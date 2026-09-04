"""Authenticated JSON tools for the ElevenLabs voice agent.

Ticket 05 owns this router. Routes / header / JSON match
``docs/voice-mvp-contracts.md`` verbatim. Wiring into ``app/main.py`` is
owned by ticket 07 — do not include this router anywhere here.

Auth: ``X-Agent-Token`` header compared with
``settings.agent_tool_token`` via ``hmac.compare_digest`` before any
business logic. All errors are ``{"error", "message"}`` — never secrets,
never stack traces.
"""

import hmac
from logging import getLogger

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.services.agent.tools import (
    ToolError,
    create_checkout_link,
    get_payment_status,
    send_email,
)

router = APIRouter(prefix="/agent/tools", tags=["agent-tools"])

logger = getLogger(__name__)


class StatusRequest(BaseModel):
    payment_id: str = Field(min_length=1, max_length=36)
    conversation_id: str = Field(min_length=1, max_length=255)


class CheckoutRequest(BaseModel):
    payment_id: str = Field(min_length=1, max_length=36)
    conversation_id: str = Field(min_length=1, max_length=255)


class EmailRequest(BaseModel):
    payment_id: str = Field(min_length=1, max_length=36)
    conversation_id: str = Field(min_length=1, max_length=255)
    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


def check_agent_token(x_agent_token: str | None, settings: Settings) -> JSONResponse | None:
    """Validate the agent token before any business logic.

    Returns None when authorized, otherwise the ``{"error", "message"}``
    response to return: 503 TOOL_DISABLED when no token is configured
    (path disabled), 401 UNAUTHORIZED for a missing/wrong token. Uses
    hmac.compare_digest to avoid timing leaks.
    """
    configured_token = settings.agent_tool_token.strip()
    if not configured_token:
        logger.error("Rejected agent tool request: tools are not configured")
        return _error(503, "TOOL_DISABLED", "Agent tools are not configured")
    if not x_agent_token or not hmac.compare_digest(x_agent_token, configured_token):
        logger.warning("Rejected agent tool request: invalid token")
        return _error(401, "UNAUTHORIZED", "Invalid agent token")
    return None


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": code, "message": message})


@router.post("/get-payment-status")
def agent_get_payment_status(
    payload: StatusRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    denied = check_agent_token(x_agent_token, settings)
    if denied is not None:
        return denied
    try:
        result = get_payment_status(db, payload.payment_id, payload.conversation_id)
        logger.info("Agent get-payment-status completed for payment %s", result["payment_id"])
        return result
    except ToolError as error:
        logger.warning("Agent get-payment-status rejected (%s)", error.code)
        return _error(error.http_status, error.code, error.message)
    except Exception:
        logger.exception("Agent get-payment-status failed")
        return _error(500, "INTERNAL_ERROR", "Payment status lookup failed")


@router.post("/create-checkout-link")
def agent_create_checkout_link(
    payload: CheckoutRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    denied = check_agent_token(x_agent_token, settings)
    if denied is not None:
        return denied
    try:
        result = create_checkout_link(db, settings, payload.payment_id, payload.conversation_id)
        logger.info("Agent create-checkout-link completed for payment %s", result["payment_id"])
        return result
    except ToolError as error:
        logger.warning("Agent create-checkout-link rejected (%s)", error.code)
        return _error(error.http_status, error.code, error.message)
    except Exception:
        logger.exception("Agent create-checkout-link failed")
        return _error(500, "INTERNAL_ERROR", "Checkout link creation failed")


@router.post("/send-email")
def agent_send_email(
    payload: EmailRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    denied = check_agent_token(x_agent_token, settings)
    if denied is not None:
        return denied
    try:
        result = send_email(db, payload.payment_id, payload.conversation_id, str(payload.to), payload.subject, payload.body)
        logger.info("Agent send-email completed for payment %s", payload.payment_id.strip())
        return result
    except ToolError as error:
        logger.warning("Agent send-email rejected (%s)", error.code)
        return _error(error.http_status, error.code, error.message)
    except Exception:
        logger.exception("Agent send-email failed")
        return _error(500, "INTERNAL_ERROR", "Email send failed")
