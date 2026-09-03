from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import Settings, get_settings
from app.core.crypto import TokenEncryptionError, encrypt_token
from app.core.database import get_db
from app.models.oauth_state import OAuthState
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.schemas.integration import ProviderConnectionResponse
from app.services.providers.base import PaymentProvider, ProviderError
from app.services.providers.razorpay import RazorpayProvider

router = APIRouter(prefix="/integrations", tags=["integrations"])


def get_razorpay_provider(settings: Settings = Depends(get_settings)) -> PaymentProvider:
    return RazorpayProvider(settings)


def optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    try:
        return current_user(request, db, settings)
    except HTTPException as error:
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def _frontend_redirect(settings: Settings, result: str) -> RedirectResponse:
    query = urlencode({"status": result})
    return RedirectResponse(
        url=f"{settings.razorpay_frontend_redirect_uri}?{query}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/razorpay/status", response_model=ProviderConnectionResponse)
def razorpay_status(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProviderConnectionResponse:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "razorpay",
        )
    )
    return ProviderConnectionResponse(
        provider="razorpay",
        connected=connection is not None and connection.status == "connected",
    )


@router.get("/razorpay/connect")
def connect_razorpay(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.razorpay_client_id or not settings.razorpay_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay integration is not configured",
        )

    raw_state = token_urlsafe(32)
    db.add(
        OAuthState(
            id=str(uuid4()),
            state_hash=sha256(raw_state.encode("utf-8")).hexdigest(),
            merchant_id=user.merchant_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.oauth_state_ttl_seconds),
        )
    )
    db.commit()

    query = urlencode(
        {
            "client_id": settings.razorpay_client_id,
            "response_type": "code",
            "redirect_uri": settings.razorpay_redirect_uri,
            "scope": settings.razorpay_scope,
            "state": raw_state,
        }
    )
    return RedirectResponse(
        url=f"{settings.razorpay_authorize_url}?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.get("/razorpay/callback")
async def razorpay_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: User | None = Depends(optional_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: PaymentProvider = Depends(get_razorpay_provider),
) -> RedirectResponse:
    if user is None:
        return _frontend_redirect(settings, "oauth_session_invalid")
    if not state:
        return _frontend_redirect(settings, "oauth_state_invalid")

    oauth_state = db.scalar(
        select(OAuthState)
        .where(OAuthState.state_hash == sha256(state.encode("utf-8")).hexdigest())
        .with_for_update()
    )
    now = datetime.now(UTC)
    expires_at = oauth_state.expires_at if oauth_state is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        oauth_state is None
        or oauth_state.merchant_id != user.merchant_id
        or oauth_state.used_at is not None
        or expires_at <= now
    ):
        return _frontend_redirect(settings, "oauth_state_invalid")

    # Consume the state before contacting Razorpay so it cannot be replayed.
    oauth_state.used_at = now
    db.commit()

    if error:
        return _frontend_redirect(settings, "oauth_access_denied")
    if not code:
        return _frontend_redirect(settings, "oauth_exchange_failed")

    try:
        token = await provider.exchange_oauth_code(code)
        if not token.provider_account_id:
            raise ProviderError("Razorpay did not return an account identifier")
        access_token_encrypted = encrypt_token(token.access_token, settings.token_encryption_key)
        if not token.refresh_token:
            raise ProviderError("Razorpay did not return a refresh token")
        refresh_token_encrypted = encrypt_token(token.refresh_token, settings.token_encryption_key)
    except (ProviderError, TokenEncryptionError):
        return _frontend_redirect(settings, "oauth_exchange_failed")

    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "razorpay",
        )
    )
    if connection is None:
        connection = ProviderConnection(
            merchant_id=user.merchant_id,
            provider="razorpay",
            provider_account_id=token.provider_account_id,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            access_token_expires_at=now + timedelta(seconds=token.expires_in),
            scopes=token.scopes or [settings.razorpay_scope],
            status="connected",
        )
        db.add(connection)
    else:
        connection.provider_account_id = token.provider_account_id
        connection.access_token_encrypted = access_token_encrypted
        connection.refresh_token_encrypted = refresh_token_encrypted
        connection.access_token_expires_at = now + timedelta(seconds=token.expires_in)
        connection.scopes = token.scopes or [settings.razorpay_scope]
        connection.status = "connected"
    db.commit()
    return _frontend_redirect(settings, "connected")
