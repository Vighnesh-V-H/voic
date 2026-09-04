"""Pure business logic for the ElevenLabs agent-tool endpoints.

Ticket 05 owns this module. It contains no FastAPI / auth code — the
``app.api.agent_tools`` router handles HTTP, headers, and error mapping,
and calls into these functions.

Email note: the agent send-email tool sends through Resend when
``RESEND_API_KEY`` + ``RESEND_FROM_EMAIL`` are configured; otherwise it
logs the request and returns a demo payload with ``demo: True``.
"""

from collections.abc import Mapping
from logging import getLogger
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.call_attempt import CallAttempt
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.provider_connection import ProviderConnection
from app.services.agent import resend as resend_email_client
from app.services.agent.resend import ResendEmailError
from app.services.providers.stripe import StripeProvider

logger = getLogger(__name__)


class ToolError(Exception):
    """Typed tool failure. Carries a stable error code, a safe message
    (never secrets / stack traces), and the HTTP status to return."""

    def __init__(self, code: str, message: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _get_payment_or_raise(db: Session, payment_id: str, conversation_id: str) -> Payment:
    normalized_id = payment_id.strip()
    normalized_conv = conversation_id.strip()
    if not normalized_conv:
        raise ToolError("MISSING_CONVERSATION_ID", "conversation_id is required", 400)
    payment = db.scalar(select(Payment).where(Payment.id == normalized_id))
    if payment is None:
        raise ToolError("PAYMENT_NOT_FOUND", "Payment not found", 404)
    active_call = db.scalar(
        select(CallAttempt).where(
            CallAttempt.payment_id == payment.id,
            CallAttempt.merchant_id == payment.merchant_id,
            CallAttempt.provider == "vobiz",
            CallAttempt.status == "BRIDGED",
        )
    )
    if active_call is None:
        raise ToolError(
            "CALL_NOT_ACTIVE",
            "Payment tools are only available during its active recovery call",
            409,
        )
    if (
        not active_call.elevenlabs_conversation_id
        or active_call.elevenlabs_conversation_id != normalized_conv
    ):
        raise ToolError(
            "CONVERSATION_MISMATCH",
            "Tool request does not belong to this call",
            403,
        )
    return payment


def _latest_customer_event(db: Session, payment: Payment) -> PaymentEvent | None:
    """Return customer data only from this payment's merchant/provider scope."""
    if not payment.provider_payment_id:
        return None
    return db.scalar(
        select(PaymentEvent)
        .where(
            PaymentEvent.merchant_id == payment.merchant_id,
            PaymentEvent.provider_connection_id == payment.provider_connection_id,
            PaymentEvent.provider == payment.provider,
            PaymentEvent.provider_payment_id == payment.provider_payment_id,
        )
        .order_by(PaymentEvent.occurred_at.desc())
        .limit(1)
    )


def _provider_value(value: object, name: str) -> object:
    """Same pattern as ``provider_value`` in ``app.api.stripe``: read a
    field off a Stripe SDK object (attribute) or a normalized dict."""
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def get_payment_status(db: Session, payment_id: str, conversation_id: str) -> dict[str, Any]:
    """Return the status snapshot the voice agent reads out to the caller.

    ``customer_email`` / ``customer_phone`` are not columns on ``payments``;
    they are tracked on ``payment_events`` by the Stripe webhook handler, so
    the latest event for this payment's ``provider_payment_id`` is used with
    a ``None`` fallback when no event exists yet.
    """
    payment = _get_payment_or_raise(db, payment_id, conversation_id)

    customer_email: str | None = None
    customer_phone: str | None = None
    latest_event = _latest_customer_event(db, payment)
    if latest_event is not None:
        customer_email = latest_event.customer_email
        customer_phone = latest_event.customer_phone

    return {
        "payment_id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
    }


def create_checkout_link(db: Session, settings: Settings, payment_id: str, conversation_id: str) -> dict[str, Any]:
    """Create a fresh Stripe Payment Link for an existing payment.

    Reuses the same provider-account scoping as
    ``POST /api/v1/payment-links`` in ``app.api.stripe``: the link is
    created on the payment's own connected Stripe account
    (``provider_connection_id`` must still be ``connected``), with the
    payment's stored ``provider_price_id`` and ``voic_payment_id`` metadata
    for webhook correlation. Never manufactures URLs — the returned URL
    always comes from Stripe.

    The new link fields are stored on the payment and its status is set to
    ``PENDING`` before returning.
    """
    payment = _get_payment_or_raise(db, payment_id, conversation_id)
    if payment.status not in {"FAILED", "PENDING"}:
        raise ToolError(
            "PAYMENT_NOT_ACTIONABLE",
            "Payment is not eligible for a recovery checkout link",
            409,
        )
    if payment.status == "PENDING" and payment.provider_payment_link_url:
        return {
            "payment_id": payment.id,
            "checkout_url": payment.provider_payment_link_url,
            "status": payment.status,
        }

    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.id == payment.provider_connection_id,
            ProviderConnection.merchant_id == payment.merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.provider_account_id == payment.provider_account_id,
            ProviderConnection.status == "connected",
        )
    )
    if connection is None:
        raise ToolError("STRIPE_NOT_CONNECTED", "Merchant Stripe account is not connected", 409)

    provider = StripeProvider(settings)

    # Stripe requires different metadata containers for one-time and recurring
    # prices, so never guess the price type after a lookup failure.
    try:
        price = provider.get_price(connection.provider_account_id, payment.provider_price_id)
        raw_type = _provider_value(price, "type")
        if raw_type not in {"one_time", "recurring"}:
            raise ValueError("Stripe price type is missing")
        price_type = str(raw_type)
    except Exception as error:
        logger.warning(
            "Agent tool price lookup failed for payment %s (%s)",
            payment.id,
            type(error).__name__,
        )
        raise ToolError(
            "STRIPE_PROVIDER_ERROR", "Stripe price lookup failed", 502
        ) from error

    metadata = {"voic_payment_id": payment.id}
    try:
        provider_link = provider.create_payment_link(
            connection.provider_account_id,
            payment.provider_price_id,
            1,
            metadata,
            f"agent-payment-link:{payment.id}",
            price_type=price_type,
        )
    except Exception as error:
        logger.warning(
            "Agent tool Payment Link creation failed for payment %s (%s)",
            payment.id,
            type(error).__name__,
        )
        raise ToolError("STRIPE_PROVIDER_ERROR", "Stripe Payment Link creation failed", 502) from error

    provider_link_id = _provider_value(provider_link, "id")
    url = _provider_value(provider_link, "url")
    if not isinstance(provider_link_id, str) or not isinstance(url, str):
        raise ToolError("STRIPE_PROVIDER_ERROR", "Stripe Payment Link creation failed", 502)

    payment.provider_payment_link_id = provider_link_id
    payment.provider_payment_link_url = url
    payment.status = "PENDING"
    db.commit()

    return {"payment_id": payment.id, "checkout_url": url, "status": payment.status}


def send_email(
    db: Session, settings: Settings, payment_id: str, conversation_id: str, to: str, subject: str, body: str
) -> dict[str, Any]:
    """Send an email related to a payment through Resend.

    Recipient is always validated against the customer email captured by
    this payment's provider events (merchant/provider scoped), never
    trusted from the request alone. When Resend is not configured the
    request is logged and a demo payload with ``demo: True`` returned;
    when it is configured the email is delivered and the Resend message
    ID is returned as ``email_id``.
    """
    payment = _get_payment_or_raise(db, payment_id, conversation_id)
    event = _latest_customer_event(db, payment)
    expected_email = event.customer_email.strip() if event and event.customer_email else ""
    if not expected_email:
        raise ToolError(
            "CUSTOMER_EMAIL_NOT_FOUND",
            "No verified customer email is available for this payment",
            409,
        )
    if expected_email.casefold() != to.strip().casefold():
        raise ToolError(
            "CUSTOMER_EMAIL_MISMATCH",
            "Email recipient does not match this payment",
            403,
        )
    domain = expected_email.rpartition("@")[2] or "unknown"
    logger.info(
        "Agent tool send-email: payment_id=%s recipient_domain=%s body_chars=%d",
        payment.id,
        domain,
        len(body),
    )
    if not resend_email_client.is_configured(settings):
        return {"sent": True, "to": expected_email, "demo": True}
    try:
        message_id = resend_email_client.send_email(settings, expected_email, subject, body)
    except ResendEmailError as error:
        logger.warning(
            "Agent tool send-email Resend failure for payment %s (%s)",
            payment.id,
            type(error).__name__,
        )
        raise ToolError("EMAIL_SEND_FAILED", "Email send failed", 502) from error
    return {"sent": True, "to": expected_email, "email_id": message_id}
