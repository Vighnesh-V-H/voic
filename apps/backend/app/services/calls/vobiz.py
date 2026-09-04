"""Vobiz outbound-call trigger for failed-payment recovery.

The Stripe webhook decides: when a payment transitions to ``FAILED`` it
enqueues :func:`trigger_recovery_call` as a background task, which places a
single outbound call to the customer phone stored on the payment event via::

    POST https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/

Required headers are ``X-Auth-ID`` / ``X-Auth-Token``; the body carries
    ``from`` (the merchant's Vobiz caller ID), ``to`` (customer phone), and a
    per-payment ``answer_url`` (serves the Voice XML flow once the call connects).

Without Vobiz credentials the trigger logs and skips so webhooks keep
working in local development. This module never raises to the webhook.
"""

import hashlib
import hmac
import json
import urllib.request
from datetime import UTC, datetime
from logging import getLogger
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import SessionLocal
from app.models.call_attempt import CallAttempt
from app.models.payment import Payment

logger = getLogger(__name__)

CALL_TRIGGER_EVENTS = frozenset({"payment_intent.payment_failed"})
VOBIZ_API_BASE = "https://api.vobiz.ai/api/v1"
REQUEST_TIMEOUT_SECONDS = 10
RECOVERY_ANSWER_PATH = "/api/v1/voice/answer"


class VobizCallError(Exception):
    """Raised when the Vobiz Make Call request fails."""


def is_configured(settings: Settings) -> bool:
    """Return True only when every voice setting needed to dial is present.

    Dialing requires the Vobiz credentials, the caller ID, and the callback
    plumbing (public base URL plus callback token) so a placed call always
    has working per-call answer/hangup URLs.
    """
    return bool(
        settings.vobiz_auth_id.strip()
        and settings.vobiz_auth_token.strip()
        and settings.vobiz_caller_id.strip()
        and settings.vobiz_public_base_url.strip()
        and settings.voice_callback_token.strip()
    )


def callback_signature(token: str, payment_id: str, attempt_id: str) -> str:
    """Return the HMAC used to bind a callback URL to one call attempt."""
    return hmac.new(
        token.encode("utf-8"),
        f"{payment_id}:{attempt_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def recovery_answer_url(settings: Settings, payment_id: str, attempt_id: str) -> str:
    """Build the authenticated, per-payment answer callback URL."""
    base_url = settings.vobiz_public_base_url.strip().rstrip("/")
    query = urlencode(
        {
            "payment_id": payment_id,
            "attempt_id": attempt_id,
            "signature": callback_signature(
                settings.voice_callback_token.strip(), payment_id, attempt_id
            ),
        }
    )
    return f"{base_url}{RECOVERY_ANSWER_PATH}?{query}"


def place_call(settings: Settings, *, to: str, payment_id: str, attempt_id: str) -> str:
    """Place one outbound call to ``to`` and return the provider call ID.

    Args:
        settings: Application settings carrying the Vobiz credentials,
            caller ID, public callback base URL, and callback token.
        to: Destination phone number in E.164 format.
        payment_id: Voic payment ID carried by the callback URL.
        attempt_id: Voic call-attempt ID bound to the callback URL.

    Returns:
        The Vobiz request/call UUID, or an empty string when absent.

    Raises:
        VobizCallError: If the request fails or the response is unusable.
    """
    url = f"{VOBIZ_API_BASE}/Account/{settings.vobiz_auth_id.strip()}/Call/"
    body = {
        "from": settings.vobiz_caller_id.strip(),
        "to": to,
        "answer_url": recovery_answer_url(settings, payment_id, attempt_id),
        "answer_method": "POST",
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "X-Auth-ID": settings.vobiz_auth_id.strip(),
            "X-Auth-Token": settings.vobiz_auth_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise VobizCallError(f"Vobiz Make Call request failed: {error}") from error
    if not isinstance(payload, dict):
        raise VobizCallError("Vobiz Make Call returned a non-object response")
    call_id = payload.get("request_uuid") or payload.get("call_uuid") or ""
    return str(call_id)


def trigger_recovery_call(
    settings: Settings,
    *,
    event_type: str,
    merchant_id: str,
    payment_id: str,
    customer_phone: str | None,
    db: Session | None = None,
) -> str:
    """Reserve, place, and persist one recovery call; never raises.

    Args:
        settings: Application settings carrying the Vobiz configuration.
        event_type: The Stripe event type that flipped the payment to FAILED.
        merchant_id: Merchant that owns the payment (for log scoping).
        payment_id: Voic payment ID the call is about.
        customer_phone: Normalized customer phone, if the event carried one.
        db: Optional database session. Webhook tasks pass their request session;
            direct workers create and close their own session.

    Returns:
        ``"called:<provider_id>"`` on success, otherwise a
        ``"skipped:<reason>"`` string describing why no call was placed.
    """
    if event_type not in CALL_TRIGGER_EVENTS:
        return "skipped:event-not-trigger"
    if not customer_phone:
        logger.info("Skipping recovery call for payment %s: no customer phone", payment_id)
        return "skipped:no-phone"
    if not is_configured(settings):
        logger.info("Skipping recovery call for payment %s: Vobiz not configured", payment_id)
        return "skipped:vobiz-not-configured"

    own_session = db is None
    session = db or SessionLocal()
    try:
        existing = session.scalar(
            select(CallAttempt).where(
                CallAttempt.merchant_id == merchant_id,
                CallAttempt.payment_id == payment_id,
            )
        )
        if existing is not None:
            return "skipped:already-attempted"

        payment = session.scalar(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.merchant_id == merchant_id,
            )
        )
        if payment is None:
            logger.info("Skipping recovery call for unknown payment %s", payment_id)
            return "skipped:payment-not-found"
        if payment.status == "COMPLETED":
            logger.info("Skipping recovery call for completed payment %s", payment_id)
            return "skipped:payment-completed"
        if payment.status != "FAILED":
            logger.info("Skipping recovery call for payment %s with status %s", payment_id, payment.status)
            return "skipped:payment-not-failed"

        attempt = CallAttempt(
            merchant_id=merchant_id,
            payment_id=payment_id,
            provider="vobiz",
            status="QUEUED",
        )
        session.add(attempt)
        try:
            # Commit the claim before the provider request. The unique key makes
            # separate webhook workers converge on one outbound call.
            session.commit()
        except IntegrityError:
            session.rollback()
            return "skipped:already-attempted"

        try:
            call_id = place_call(
                settings,
                to=customer_phone,
                payment_id=payment_id,
                attempt_id=attempt.id,
            )
        except VobizCallError:
            logger.exception("Recovery call failed for payment %s", payment_id)
            attempt.status = "FAILED"
            attempt.closed_at = datetime.now(UTC)
            session.commit()
            return "skipped:vobiz-error"

        attempt.provider_call_id = call_id or None
        attempt.status = "PLACED"
        attempt.placed_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "Triggered Vobiz recovery call for merchant %s payment %s (provider_id=%s)",
            merchant_id,
            payment_id,
            call_id,
        )
        return f"called:{call_id}"
    except Exception:
        session.rollback()
        logger.exception("Could not persist recovery call for payment %s", payment_id)
        return "skipped:database-error"
    finally:
        if own_session:
            session.close()
