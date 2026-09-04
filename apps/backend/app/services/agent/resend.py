"""Resend transactional-email client for the agent send-email tool.

Thin wrapper over the Resend HTTP API (no SDK dependency). Raises
``ResendEmailError`` on any unusable request/response so callers can map
it to a typed tool error. Never logs or raises with the API key.
"""

import json
import urllib.request
from logging import getLogger

from app.core.config import Settings

logger = getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT_SECONDS = 10


class ResendEmailError(Exception):
    """Raised when the Resend send request fails or the response is unusable."""


def is_configured(settings: Settings) -> bool:
    """Return True only when both the API key and a from-address are set."""
    return bool(settings.resend_api_key.strip() and settings.resend_from_email.strip())


def send_email(settings: Settings, to: str, subject: str, body: str) -> str:
    """Send one plain-text email through Resend and return the message ID."""
    request = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(
            {
                "from": settings.resend_from_email.strip(),
                "to": [to.strip()],
                "subject": subject,
                "text": body,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise ResendEmailError(f"Resend send request failed: {error}") from error
    if not isinstance(payload, dict):
        raise ResendEmailError("Resend send returned a non-object response")
    message_id = payload.get("id", "")
    if not message_id:
        raise ResendEmailError("Resend send response missing message id")
    return str(message_id)
