import json
from collections.abc import Mapping
from datetime import UTC, datetime
from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.services.providers.stripe import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = getLogger(__name__)


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
    amount: int | None
    currency: str | None
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


def payment_for_event(
    db: Session,
    merchant_id: str,
    connection: ProviderConnection,
    provider_payment_id: str | None,
    metadata: Mapping[str, object],
) -> Payment | None:
    """
    Locate a payment record matching the event's metadata or provider payment ID.

    Args:
        db: Database session for querying payment records.
        merchant_id: The merchant ID owning the payment.
        connection: The provider connection associated with the event.
        provider_payment_id: The provider's payment ID from the event.
        metadata: The event metadata containing voic_payment_id.

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
    if provider_payment_id is None:
        return None
    return db.scalar(
        select(Payment).where(
            Payment.provider == "stripe",
            Payment.provider_payment_id == provider_payment_id,
            Payment.merchant_id == merchant_id,
            Payment.provider_connection_id == connection.id,
            Payment.provider_account_id == connection.provider_account_id,
        )
    )


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
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
    if not verify_webhook_signature(payload, signature, settings.stripe_connect_webhook_secret):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_SIGNATURE")
    try:
        event = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD") from error
    if not isinstance(event, Mapping):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")

    event_id = event.get("id")
    event_type = event.get("type")
    account_id = event.get("account")
    if not all(isinstance(value, str) and value for value in (event_id, event_type, account_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.provider == "stripe",
            ProviderConnection.provider_account_id == account_id,
        )
    )
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
    duplicate = db.scalar(
        select(PaymentEvent).where(
            PaymentEvent.provider == "stripe", PaymentEvent.provider_event_id == event_id
        )
    )
    if duplicate is not None:
        return {"status": "duplicate"}

    data = event.get("data")
    event_object = data.get("object") if isinstance(data, Mapping) else None
    if not isinstance(event_object, Mapping):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_INVALID_PAYLOAD")
    provider_payment_id = event_object.get("id")
    provider_payment_id = provider_payment_id if isinstance(provider_payment_id, str) else None
    metadata = event_object.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    amount = event_object.get("amount")
    amount = amount if isinstance(amount, int) else None
    currency = event_object.get("currency")
    currency = currency if isinstance(currency, str) else None
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
        customer_reference=None,
        raw_payload=payload.decode("utf-8"),
        occurred_at=occurred_at,
        received_at=now,
        processed_at=now,
    )
    db.add(payment_event)

    if event_type in {"payment_intent.succeeded", "payment_intent.payment_failed"}:
        payment = payment_for_event(db, connection.merchant_id, connection, provider_payment_id, metadata)
        if payment is not None:
            last_event_at = payment.last_event_at
            if last_event_at is not None and last_event_at.tzinfo is None:
                last_event_at = last_event_at.replace(tzinfo=UTC)
            next_status = "COMPLETED" if event_type.endswith("succeeded") else "FAILED"
            if (
                last_event_at is None
                or occurred_at > last_event_at
                or (occurred_at == last_event_at and next_status == "COMPLETED")
            ):
                payment.status = next_status
                payment.last_event_at = occurred_at
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
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
    """
    events = db.scalars(
        select(PaymentEvent)
        .where(PaymentEvent.merchant_id == user.merchant_id)
        .order_by(PaymentEvent.occurred_at.desc())
        .limit(50)
    ).all()
    return [PaymentEventResponse.model_validate(event, from_attributes=True) for event in events]
