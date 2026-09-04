from hmac import compare_digest
from urllib.parse import urlencode

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


def stream_voice_xml(ws_url: str, fallback_message: str) -> str:
    """Build the bidirectional-stream answer XML for a recovery call.

    Vobiz connects back to ``ws_url`` (which carries the call-attempt id)
    and forks live audio over it. If the stream cannot start, Vobiz falls
    through to the ``Speak`` fallback instead of dropping the caller.
    """
    from xml.sax.saxutils import escape

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Stream bidirectional="true" keepCallAlive="true" '
        'contentType="audio/x-mulaw;rate=8000">'
        f"{escape(ws_url)}"
        "</Stream>"
        f"<Speak>{escape(fallback_message)}</Speak>"
        "</Response>"
    )


def ws_base_url(settings: Settings) -> str:
    """Public wss host for media streams, explicit setting or derived."""
    explicit = (settings.voice_ws_base_url or "").strip().rstrip("/")
    if explicit:
        return explicit
    public = (settings.vobiz_public_base_url or "").strip().rstrip("/")
    if public.startswith("https://"):
        return "wss://" + public.removeprefix("https://")
    if public.startswith("http://"):
        return "ws://" + public.removeprefix("http://")
    return ""


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
        callable_statuses = {"FAILED"}
        if settings.voice_demo_success_trigger:
            callable_statuses.add("COMPLETED")
        payment = db.scalar(
            select(Payment)
            .join(
                CallAttempt,
                (CallAttempt.payment_id == Payment.id)
                & (CallAttempt.merchant_id == Payment.merchant_id),
            )
            .where(
                Payment.id == payment_id,
                Payment.status.in_(callable_statuses),
                CallAttempt.id == attempt_id,
                CallAttempt.provider == "vobiz",
            )
        )

    message = RECOVERY_MESSAGE if payment is not None else SAFE_FALLBACK
    if payment is None:
        return Response(content=recovery_voice_xml(message), media_type="application/xml")
    base = ws_base_url(settings)
    if not base:
        return Response(content=recovery_voice_xml(message), media_type="application/xml")
    stream_query = urlencode(
        {
            "payment_id": payment.id,
            "signature": callback_signature(expected_token, payment.id, attempt_id),
        }
    )
    return Response(
        content=stream_voice_xml(
            f"{base}/ws/voice/{attempt_id}?{stream_query}", message
        ),
        media_type="application/xml",
    )
