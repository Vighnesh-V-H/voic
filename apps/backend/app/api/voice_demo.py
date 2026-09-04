"""Demo shortcut: trigger a recovery voice call without a Stripe webhook.

DEMO ONLY — lets the 3-hour demo dial a call for a known payment without
replaying a real `payment_intent.payment_failed` event. Production keeps the
webhook-driven FAILED-transition rule. Ticket 07 wires this router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.call_attempt import CallAttempt
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.user import User
from app.services.calls import vobiz as vobiz_calls

router = APIRouter(prefix="/voice", tags=["voice"])


class DemoTriggerRequest(BaseModel):
    payment_id: str
    phone: str | None = None


@router.post("/demo-trigger")
def demo_trigger(
    payload: DemoTriggerRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str | None]:
    """Place the recovery call path for a merchant-owned payment on demand."""
    payment = db.scalar(
        select(Payment).where(
            Payment.id == payload.payment_id.strip(),
            Payment.merchant_id == user.merchant_id,
        )
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PAYMENT_NOT_FOUND")

    phone = (payload.phone or "").strip() or None
    if phone is None and payment.provider_payment_id:
        event = db.scalar(
            select(PaymentEvent)
            .where(
                PaymentEvent.merchant_id == user.merchant_id,
                PaymentEvent.provider_payment_id == payment.provider_payment_id,
                PaymentEvent.customer_phone.is_not(None),
            )
            .order_by(PaymentEvent.occurred_at.desc())
        )
        phone = event.customer_phone if event is not None else None
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="NO_CUSTOMER_PHONE",
        )

    result = vobiz_calls.trigger_recovery_call(
        settings,
        event_type="payment_intent.payment_failed",
        merchant_id=user.merchant_id,
        payment_id=payment.id,
        customer_phone=phone,
        db=db,
    )
    attempt = db.scalar(
        select(CallAttempt).where(
            CallAttempt.merchant_id == user.merchant_id,
            CallAttempt.payment_id == payment.id,
        )
    )
    return {
        "result": result,
        "call_id": attempt.id if attempt is not None else None,
        "status": attempt.status if attempt is not None else None,
    }
