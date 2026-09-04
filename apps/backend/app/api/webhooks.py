import json
from collections.abc import Mapping
from datetime import UTC, datetime
from logging import getLogger

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.api.auth import current_user
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.services.calls import vobiz as vobiz_calls
from app.services.providers.stripe import StripeProvider, verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = getLogger(__name__)
ACCOUNT_LESS_IGNORED_PREFIXES = ("payment_method.", "mandate.")
PAYMENT_SUCCESS_EVENTS = {
    "charge.succeeded",
    "checkout.session.completed",
    "invoice.paid",
    "invoice.payment_succeeded",
    "invoice_payment.paid",
    "payment_intent.succeeded",
}
PAYMENT_FAILURE_EVENTS = {
    "charge.failed",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
    "invoice.payment_failed",
    "invoice_payment.failed",
    "payment_intent.payment_failed",
}
STORED_EVENT_TYPES = {
    "checkout.session.completed",
    "payment_intent.payment_failed",
}


def delete_merchant_stripe_data(db: Session, merchant_id: str) -> None:
    """
    Remove all Voic-owned Stripe data for a merchant.

    Deletes payment events, payments, then provider connections for
    provider ``stripe``. The merchant and user records are preserved so
    the merchant stays logged in.

    Args:
        db: Database session for deleting records.
        merchant_id: The merchant whose Stripe data should be removed.
    """
    db.execute(
        delete(PaymentEvent).where(
            PaymentEvent.merchant_id == merchant_id,
            PaymentEvent.provider == "stripe",
        )
    )
    db.execute(
        delete(Payment).where(
            Payment.merchant_id == merchant_id,
            Payment.provider == "stripe",
        )
    )
    db.execute(
        delete(ProviderConnection).where(
            ProviderConnection.merchant_id == merchant_id,
            ProviderConnection.provider == "stripe",
        )
    )


class PaymentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_event_id: str
    event_type: str
    provider_payment_id: str | None
    provider_price_id: str | None
    amount: int | None
    currency: str | None
    customer_reference: str | None
    customer_email: str | None
    customer_phone: str | None
    payment_status: str | None
    occurred_at: datetime


def event_time(value: object) -> datetime:
    """
    Convert a timestamp value to a timezone-aware datetime or return the current time.

    Args:
        value: A Unix timestamp (int or float) or any other object.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    return datetime.now(UTC)


def object_id(value: object) -> str | None:
    """Return a provider object ID from an expanded object or plain ID."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        candidate = value.get("id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def customer_data(
    event_object: Mapping[str, object],
    metadata: Mapping[str, object],
    payment_method_details: Mapping[str, object] | None = None,
    customer_details: Mapping[str, object] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Extract safe, normalized customer contact fields from common Stripe objects."""
    event_customer_details = event_object.get("customer_details")
    event_customer_details = event_customer_details if isinstance(event_customer_details, Mapping) else {}
    customer_details = customer_details if isinstance(customer_details, Mapping) else {}
    billing_details = event_object.get("billing_details")
    billing_details = billing_details if isinstance(billing_details, Mapping) else {}
    payment_method = event_object.get("payment_method")
    payment_method = (
        payment_method
        if isinstance(payment_method, Mapping)
        else payment_method_details
        if isinstance(payment_method_details, Mapping)
        else {}
    )
    payment_method_billing = payment_method.get("billing_details")
    payment_method_billing = payment_method_billing if isinstance(payment_method_billing, Mapping) else {}
    last_payment_error = event_object.get("last_payment_error")
    last_payment_error = last_payment_error if isinstance(last_payment_error, Mapping) else {}
    failed_payment_method = last_payment_error.get("payment_method")
    failed_payment_method = failed_payment_method if isinstance(failed_payment_method, Mapping) else {}
    failed_billing = failed_payment_method.get("billing_details")
    failed_billing = failed_billing if isinstance(failed_billing, Mapping) else {}
    shipping = event_object.get("shipping")
    shipping = shipping if isinstance(shipping, Mapping) else {}
    charges = event_object.get("charges")
    first_charge = {}
    if isinstance(charges, Mapping) and isinstance(charges.get("data"), list) and charges["data"]:
        first_charge = charges["data"][0] if isinstance(charges["data"][0], Mapping) else {}
    charge_billing = first_charge.get("billing_details")
    charge_billing = charge_billing if isinstance(charge_billing, Mapping) else {}

    def first_string(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def metadata_values(*aliases: str) -> list[object]:
        normalized_aliases = set(aliases)
        values: list[object] = []
        for key, value in metadata.items():
            if not isinstance(key, str):
                continue
            normalized_key = "".join(character.lower() for character in key if character.isalnum())
            if normalized_key in normalized_aliases:
                values.append(value)
        return values

    email = first_string(
        event_object.get("receipt_email"),
        event_object.get("customer_email"),
        event_object.get("email"),
        event_customer_details.get("email"),
        customer_details.get("email"),
        billing_details.get("email"),
        payment_method_billing.get("email"),
        charge_billing.get("email"),
        failed_billing.get("email"),
        shipping.get("email"),
        *metadata_values("customeremail", "email", "emailaddress", "customeremailaddress"),
    )
    phone = first_string(
        event_object.get("customer_phone"),
        event_object.get("phone"),
        event_customer_details.get("phone"),
        customer_details.get("phone"),
        billing_details.get("phone"),
        payment_method_billing.get("phone"),
        charge_billing.get("phone"),
        failed_billing.get("phone"),
        shipping.get("phone"),
        *metadata_values(
            "customerphone",
            "phone",
            "customerphonenumber",
            "phonenumber",
            "customernumber",
            "number",
            "customermobile",
            "mobile",
            "customermobilenumber",
            "mobilenumber",
            "contactnumber",
        ),
    )
    reference = first_string(object_id(event_object.get("customer")), metadata.get("customer_id"))
    return reference, email, phone


def payment_method_id(event_object: Mapping[str, object]) -> str | None:
    """Find a PaymentMethod ID when Stripe did not expand the PaymentMethod."""
    candidate = object_id(event_object.get("payment_method"))
    if candidate is not None:
        return candidate if candidate.startswith("pm_") else None
    last_payment_error = event_object.get("last_payment_error")
    if isinstance(last_payment_error, Mapping):
        candidate = object_id(last_payment_error.get("payment_method"))
        if candidate is not None and candidate.startswith("pm_"):
            return candidate
    return None


def normalized_payment_status(event_type: str, event_object: Mapping[str, object]) -> str | None:
    """Map a received Stripe event to Voic's normalized payment outcome."""
    if event_type == "checkout.session.completed":
        if event_object.get("payment_status") == "paid" or event_object.get("status") == "complete":
            return "COMPLETED"
        return None
    if event_type in PAYMENT_SUCCESS_EVENTS:
        return "COMPLETED"
    if event_type in PAYMENT_FAILURE_EVENTS:
        return "FAILED"
    return None


def payment_for_event(
    db: Session,
    merchant_id: str,
    connection: ProviderConnection,
    provider_payment_id: str | None,
    metadata: Mapping[str, object],
    provider_payment_link_id: str | None = None,
    provider_subscription_id: str | None = None,
    provider_invoice_id: str | None = None,
) -> Payment | None:
    """
    Locate a payment record matching the event's metadata, subscription,
    invoice, provider payment ID, or payment link ID.

    Args:
        db: Database session for querying payment records.
        merchant_id: The merchant ID owning the payment.
        connection: The provider connection associated with the event.
        provider_payment_id: The provider's payment ID from the event.
        metadata: The event metadata containing voic_payment_id.
        provider_payment_link_id: Optional provider payment link ID from checkout sessions.
        provider_subscription_id: Optional provider subscription ID from subscription-mode events.
        provider_invoice_id: Optional provider invoice ID from invoice events.

    Returns:
        The matching Payment record or None if not found.
    """
    local_payment_id = metadata.get("voic_payment_id")
    if isinstance(local_payment_id, str):
        payment = db.scalar(
            select(Payment).where(
                Payment.id == local_payment_id,
                Payment.merchant_id == merchant_id,
                Payment.provider_connection_id == connection.id,
                Payment.provider_account_id == connection.provider_account_id,
            )
        )
        if payment is not None:
            return payment
    if provider_subscription_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_subscription_id == provider_subscription_id,
                Payment.merchant_id == merchant_id,
                Payment.provider_connection_id == connection.id,
                Payment.provider_account_id == connection.provider_account_id,
            )
        )
        if payment is not None:
            return payment
    if provider_invoice_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_invoice_id == provider_invoice_id,
                Payment.merchant_id == merchant_id,
                Payment.provider_connection_id == connection.id,
                Payment.provider_account_id == connection.provider_account_id,
            )
        )
        if payment is not None:
            return payment
    if provider_payment_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_payment_id == provider_payment_id,
                Payment.merchant_id == merchant_id,
                Payment.provider_connection_id == connection.id,
                Payment.provider_account_id == connection.provider_account_id,
            )
        )
        if payment is not None:
            return payment
    if provider_payment_link_id is not None:
        return db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_payment_link_id == provider_payment_link_id,
                Payment.merchant_id == merchant_id,
                Payment.provider_connection_id == connection.id,
                Payment.provider_account_id == connection.provider_account_id,
            )
        )
    return None


def subscription_ref(event_object: Mapping[str, object]) -> str | None:
    """
    Extract a Stripe subscription ID from a Checkout Session or invoice object.

    Handles both the legacy top-level ``subscription`` field and the newer
    ``parent.subscription_details.subscription`` shape on invoices. Values may
    be plain IDs or expanded objects; anything else yields None.

    Args:
        event_object: The Stripe event's data object.

    Returns:
        The subscription ID or None if the event carries none.
    """
    candidate: object = event_object.get("subscription")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("id")
    if isinstance(candidate, str) and candidate:
        return candidate
    parent = event_object.get("parent")
    if isinstance(parent, Mapping):
        details = parent.get("subscription_details")
        if isinstance(details, Mapping):
            candidate = details.get("subscription")
            if isinstance(candidate, Mapping):
                candidate = candidate.get("id")
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def invoice_ref(event_object: Mapping[str, object]) -> str | None:
    """
    Extract a Stripe invoice ID from a Checkout Session or invoice-payment object.

    Values may be plain IDs or expanded objects; anything else yields None.

    Args:
        event_object: The Stripe event's data object.

    Returns:
        The invoice ID or None if the event carries none.
    """
    candidate: object = event_object.get("invoice")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("id")
    if isinstance(candidate, str) and candidate:
        return candidate
    return None


def payment_for_provider_ref(
    db: Session,
    provider_payment_id: str | None,
    provider_payment_link_id: str | None,
    provider_subscription_id: str | None,
    provider_invoice_id: str | None = None,
) -> Payment | None:
    """
    Locate any Voic payment by a Stripe-asserted provider reference.

    Used only when the signed event envelope carries no connected account, so
    the merchant boundary cannot be resolved the primary way. Unlike metadata
    (a merchant-controlled string), these references are Stripe-asserted facts
    about which provider object the event concerns, and each provider object
    belongs to exactly one connected account. Never consults metadata.

    Args:
        db: Database session for querying payment records.
        provider_payment_id: The provider payment ID from the event.
        provider_payment_link_id: The provider payment link ID from the event.
        provider_subscription_id: The provider subscription ID from the event.
        provider_invoice_id: The provider invoice ID from the event.

    Returns:
        The matching Payment record or None if no stored reference matches.
    """
    if provider_payment_link_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_payment_link_id == provider_payment_link_id,
            )
        )
        if payment is not None:
            return payment
    if provider_subscription_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_subscription_id == provider_subscription_id,
            )
        )
        if payment is not None:
            return payment
    if provider_invoice_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_invoice_id == provider_invoice_id,
            )
        )
        if payment is not None:
            return payment
    if provider_payment_id is not None:
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_payment_id == provider_payment_id,
            )
        )
        if payment is not None:
            return payment
    return None


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """
    Handle incoming Stripe Connect webhook events, verify signature, and process payment-related events.

    Args:
        request: The incoming webhook request containing the event payload and signature.
        db: Database session for persisting payment events and updating payment status.
        settings: Application settings containing the webhook secret.

    Returns:
        A dictionary indicating the processing result: ``processed``,
        ``duplicate``, or ``ignored`` for unknown/disconnected accounts.

    Raises:
        HTTPException: If signature verification fails or payload is invalid.
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    configured_secrets = [
        secret.strip()
        for secret in (settings.stripe_connect_webhook_secret or "").split(",")
        if secret.strip()
    ]
    if not any(
        verify_webhook_signature(payload, signature, secret) for secret in configured_secrets
    ):
        logger.warning("Rejecting Stripe webhook: invalid signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_SIGNATURE")
    try:
        event = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("Rejecting Stripe webhook: body is not valid JSON")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD") from error
    if not isinstance(event, Mapping):
        logger.warning("Rejecting Stripe webhook: payload is not a JSON object")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")

    event_id = event.get("id")
    event_type = event.get("type")
    account_id = object_id(event.get("account")) or object_id(event.get("context"))

    data = event.get("data")
    event_object = data.get("object") if isinstance(data, Mapping) else None
    metadata = event_object.get("metadata") if isinstance(event_object, Mapping) else None
    metadata = metadata if isinstance(metadata, Mapping) else {}

    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str) or not event_type:
        logger.warning("Rejecting Stripe webhook: missing event id or type")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")
    if account_id is None and event_type.startswith(ACCOUNT_LESS_IGNORED_PREFIXES):
        logger.info("Ignoring %s event without account: no payment semantics", event_type)
        return {"status": "ignored"}

    provider_payment_id: str | None = None
    payment_link_id: str | None = None
    subscription_id: str | None = None
    invoice_id: str | None = None
    if isinstance(event_object, Mapping):
        provider_payment_id = object_id(event_object.get("id"))
        payment_link_id = event_object.get("payment_link")
        related_payment_intent = object_id(event_object.get("payment_intent"))
        if event_type.startswith("invoice_payment."):
            payment = event_object.get("payment")
            related_payment_intent = (
                object_id(payment.get("payment_intent")) if isinstance(payment, Mapping) else None
            )
        if related_payment_intent is not None:
            provider_payment_id = related_payment_intent
        elif event_type.startswith(("checkout.session.", "invoice.", "invoice_payment.")):
            # Session, invoice, and invoice-payment IDs are not PaymentIntent IDs.
            provider_payment_id = None
        subscription_id = subscription_ref(event_object)
        invoice_id = invoice_ref(event_object)

    provider_payment_id = provider_payment_id if isinstance(provider_payment_id, str) else None
    payment_link_id = payment_link_id if isinstance(payment_link_id, str) else None
    connection: ProviderConnection | None = None
    if account_id is not None:
        connection = db.scalar(
            select(ProviderConnection).where(
                ProviderConnection.provider == "stripe",
                ProviderConnection.provider_account_id == account_id,
            )
        )
    else:
        configured_account_id = (settings.stripe_webhook_account_id or "").strip()
        hint = payment_for_provider_ref(db, provider_payment_id, payment_link_id, subscription_id, invoice_id)
        if hint is not None:
            connection = db.scalar(
                select(ProviderConnection).where(
                    ProviderConnection.id == hint.provider_connection_id,
                    ProviderConnection.provider == "stripe",
                )
            )
        if connection is None:
            if configured_account_id:
                connection = db.scalar(
                    select(ProviderConnection).where(
                        ProviderConnection.provider == "stripe",
                        ProviderConnection.provider_account_id == configured_account_id,
                    )
                )
        if connection is None and not configured_account_id:
            # A single connected account is an unambiguous local-dev fallback.
            # Production Connect webhooks should always carry account/context.
            connections = db.scalars(
                select(ProviderConnection).where(
                    ProviderConnection.provider == "stripe",
                    ProviderConnection.status == "connected",
                )
            ).all()
            if len(connections) == 1:
                connection = connections[0]
        if connection is None:
            logger.warning(
                "Rejecting Stripe webhook: unroutable event id=%s type=%s (no signed account, unknown provider references)",
                event_id,
                event_type,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")
    if event_type == "account.application.deauthorized":
        if connection is None:
            logger.info("Ignoring deauthorized event for unknown account %s", account_id)
            return {"status": "ignored"}
        delete_merchant_stripe_data(db, connection.merchant_id)
        db.commit()
        logger.info("Removed Stripe data for merchant %s after deauthorization", connection.merchant_id)
        return {"status": "processed"}
    if connection is None or connection.status != "connected":
        logger.info("Ignoring %s event for unknown/disconnected account %s", event_type, account_id)
        return {"status": "ignored"}
    if event_type not in STORED_EVENT_TYPES:
        logger.info("Ignoring %s event: not in stored allowlist", event_type)
        return {"status": "ignored"}
    duplicate = db.scalar(
        select(PaymentEvent).where(
            PaymentEvent.provider == "stripe", PaymentEvent.provider_event_id == event_id
        )
    )
    if duplicate is not None:
        return {"status": "duplicate"}

    if not isinstance(event_object, Mapping):
        logger.warning(
            "Rejecting Stripe webhook: event %s has no data object",
            event_id,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")

    amount = event_object.get("amount")
    if amount is None and isinstance(event_object.get("amount_total"), int):
        amount = event_object.get("amount_total")
    if amount is None and isinstance(event_object.get("amount_paid"), int):
        amount = event_object.get("amount_paid")
    if amount is None and isinstance(event_object.get("amount_due"), int):
        amount = event_object.get("amount_due")
    if amount is None and isinstance(event_object.get("amount_requested"), int):
        amount = event_object.get("amount_requested")
    amount = amount if isinstance(amount, int) else None
    currency = event_object.get("currency")
    currency = currency if isinstance(currency, str) else None
    customer_reference, customer_email, customer_phone = customer_data(event_object, metadata)
    if (
        (customer_email is None or customer_phone is None)
        and settings.stripe_platform_secret_key
        and event_type.startswith(("payment_intent.", "charge."))
    ):
        provider = StripeProvider(settings)
        method_id = payment_method_id(event_object)
        if method_id is not None:
            try:
                payment_method = provider.get_payment_method(connection.provider_account_id, method_id)
                _, method_email, method_phone = customer_data(payment_method, {})
                customer_email = customer_email or method_email
                customer_phone = customer_phone or method_phone
            except Exception:
                logger.warning("Could not retrieve PaymentMethod for Stripe webhook event=%s", event_id)
        customer_id = object_id(event_object.get("customer"))
        if customer_id is not None and (customer_email is None or customer_phone is None):
            try:
                customer = provider.get_customer(connection.provider_account_id, customer_id)
                _, customer_email_from_stripe, customer_phone_from_stripe = customer_data(customer, {})
                customer_email = customer_email or customer_email_from_stripe
                customer_phone = customer_phone or customer_phone_from_stripe
            except Exception:
                logger.warning("Could not retrieve Customer for Stripe webhook event=%s", event_id)
    now = datetime.now(UTC)
    occurred_at = event_time(event.get("created"))
    payment_event = PaymentEvent(
        merchant_id=connection.merchant_id,
        provider_connection_id=connection.id,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        provider_payment_id=provider_payment_id,
        amount=amount,
        currency=currency,
        customer_reference=customer_reference,
        customer_email=customer_email,
        customer_phone=customer_phone,
        payment_status=normalized_payment_status(event_type, event_object),
        raw_payload=payload.decode("utf-8"),
        occurred_at=occurred_at,
        received_at=now,
        processed_at=now,
    )
    db.add(payment_event)

    payment: Payment | None = None
    failed_transition = False
    if event_type == "payment_intent.payment_failed":
        payment = payment_for_event(
            db, connection.merchant_id, connection, provider_payment_id, metadata, payment_link_id
        )
        if payment is not None:
            if payment.provider_payment_id is None and provider_payment_id is not None:
                payment.provider_payment_id = provider_payment_id
            last_event_at = payment.last_event_at
            if last_event_at is not None and last_event_at.tzinfo is None:
                last_event_at = last_event_at.replace(tzinfo=UTC)
            if last_event_at is None or occurred_at > last_event_at:
                payment.status = "FAILED"
                payment.last_event_at = occurred_at
                failed_transition = True
    elif event_type == "checkout.session.completed":
        payment = payment_for_event(
            db, connection.merchant_id, connection, provider_payment_id, metadata, payment_link_id,
            subscription_id, invoice_id,
        )
        if payment is not None:
            if (
                payment.provider_payment_id is None
                and provider_payment_id is not None
                and provider_payment_id.startswith("pi_")
            ):
                # Only real PaymentIntent IDs; session IDs (cs_*) must not
                # pollute the column or later PI events won't correlate.
                payment.provider_payment_id = provider_payment_id
            if payment.provider_subscription_id is None and subscription_id is not None:
                # Subscription-mode checkout: remember the subscription so later
                # invoice events (which carry no payment metadata) correlate.
                payment.provider_subscription_id = subscription_id
            if payment.provider_invoice_id is None and invoice_id is not None:
                # Initial invoice of a subscription-mode checkout.
                payment.provider_invoice_id = invoice_id
            last_event_at = payment.last_event_at
            if last_event_at is not None and last_event_at.tzinfo is None:
                last_event_at = last_event_at.replace(tzinfo=UTC)
            payment_status = event_object.get("payment_status")
            checkout_status = event_object.get("status")
            if payment_status == "paid" or checkout_status == "complete":
                next_status = "COMPLETED"
            else:
                next_status = None

            if next_status is not None and (
                last_event_at is None
                or occurred_at > last_event_at
                or (occurred_at == last_event_at and next_status == "COMPLETED")
            ):
                payment.status = next_status
                payment.last_event_at = occurred_at
    if payment is not None and payment.provider_price_id:
        # Attribute the event to the Voic price so the UI can map it to a product.
        payment_event.provider_price_id = payment.provider_price_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    if failed_transition and payment is not None:
        # Call trigger: this event flipped the payment to FAILED, so enqueue
        # one Vobiz recovery call. Runs after the response; the trigger
        # itself decides (phone present, Vobiz configured) and never raises.
        background.add_task(
            vobiz_calls.trigger_recovery_call,
            settings,
            event_type=event_type,
            merchant_id=connection.merchant_id,
            payment_id=payment.id,
            customer_phone=customer_phone,
        )
    return {"status": "processed"}


@router.get("/payment-events", response_model=list[PaymentEventResponse])
def list_payment_events(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PaymentEventResponse]:
    """
    List recent payment events for the authenticated merchant.

    Args:
        user: The authenticated user making the request.
        db: Database session for querying payment events.

    Returns:
        A list of up to 50 most recent payment events, ordered by occurred_at descending.
        Only checkout.session.completed and payment_intent.payment_failed are returned.
    """
    events = db.scalars(
        select(PaymentEvent)
        .where(
            PaymentEvent.merchant_id == user.merchant_id,
            PaymentEvent.event_type.in_(STORED_EVENT_TYPES),
        )
        .order_by(PaymentEvent.occurred_at.desc())
        .limit(50)
    ).all()
    return [PaymentEventResponse.model_validate(event, from_attributes=True) for event in events]


def create_stripe_payment_link(
    connection: ProviderConnection,
    price_id: str,
    voic_payment_id: str,
    customer_email: str,
    customer_phone: str,
) -> str:
    """
    Create a Stripe Payment Link on a merchant's connected account, tagged
    with tracking metadata that will propagate onto the resulting
    PaymentIntent so the webhook above can correlate it back to ``Payment``.

    Args:
        connection: The merchant's Stripe ProviderConnection (Connect account).
        price_id: An existing Stripe Price ID on the merchant's account.
        voic_payment_id: Voic's internal Payment.id, used for correlation.
        customer_email: The customer's email, stored as tracking metadata.
        customer_phone: The customer's phone, stored as tracking metadata.

    Returns:
        The hosted URL of the created Payment Link.
    """
    import stripe

    tracking_metadata = {
        "voic_payment_id": voic_payment_id,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
    }
    link = stripe.PaymentLink.create(
        line_items=[{"price": price_id, "quantity": 1}],
        metadata=tracking_metadata,

        payment_intent_data={"metadata": tracking_metadata},
        stripe_account=connection.provider_account_id,
    )
    return link.url
