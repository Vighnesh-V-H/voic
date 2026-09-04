from hmac import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.call_attempt import CallAttempt
from app.models.payment import Payment
from app.services.calls.vobiz import callback_signature

router = APIRouter(prefix="/voice", tags=["voice"])

SAFE_FALLBACK = (
    "We could not verify this payment reminder. Please contact the merchant for help. Goodbye."
)
RECOVERY_MESSAGE = (
    "This is a reminder that your recent payment could not be completed. "
    "Please contact the merchant to complete your payment. Goodbye."
)


def recovery_voice_xml(message: str) -> str:
    """Build the small, deterministic Vobiz XML document used by callbacks."""
    from xml.sax.saxutils import escape

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Speak>{escape(message)}</Speak>"
        "<Hangup/>"
        "</Response>"
    )


@router.api_route("/answer", methods=["GET", "POST"])
def answer_call(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return a payment-specific recovery flow to an authenticated Vobiz call."""
    expected_token = settings.voice_callback_token.strip()
    payment_id = request.query_params.get("payment_id", "").strip()
    attempt_id = request.query_params.get("attempt_id", "").strip()
    supplied_signature = request.query_params.get("signature", "")
    expected_signature = (
        callback_signature(expected_token, payment_id, attempt_id) if expected_token else ""
    )
    if not expected_token or not compare_digest(supplied_signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VOICE_CALLBACK_UNAUTHORIZED",
        )

    payment = None
    if payment_id and attempt_id:
        payment = db.scalar(
            select(Payment)
            .join(
                CallAttempt,
                (CallAttempt.payment_id == Payment.id)
                & (CallAttempt.merchant_id == Payment.merchant_id),
            )
            .where(
                Payment.id == payment_id,
                Payment.status == "FAILED",
                CallAttempt.id == attempt_id,
                CallAttempt.provider == "vobiz",
            )
        )

    message = RECOVERY_MESSAGE if payment is not None else SAFE_FALLBACK
    return Response(content=recovery_voice_xml(message), media_type="application/xml")
