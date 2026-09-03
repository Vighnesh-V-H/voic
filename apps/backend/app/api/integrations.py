from datetime import UTC, datetime, timedelta
from venv import logger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import Settings, get_settings
from app.core.crypto import TokenEncryptionError, encrypt_token
from app.core.database import get_db
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.schemas.integration import ProviderConnectionResponse
from app.services.providers.base import PaymentProvider, PaymentProviderError
from app.services.providers.paypal import PayPalProvider

router = APIRouter(prefix="/integrations", tags=["integrations"])


def get_paypal_provider(settings: Settings = Depends(get_settings)) -> PaymentProvider:
    return PayPalProvider(settings)


def _paypal_connection(db: Session, merchant_id: str) -> ProviderConnection | None:
    return db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == merchant_id,
            ProviderConnection.provider == "paypal",
        )
    )


@router.get("/paypal/status", response_model=ProviderConnectionResponse)
def paypal_status(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProviderConnectionResponse:
    connection = _paypal_connection(db, user.merchant_id)
    return ProviderConnectionResponse(
        provider="paypal",
        connected=connection is not None and connection.status == "connected",
    )


@router.post("/paypal/connect", response_model=ProviderConnectionResponse)
async def connect_paypal(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: PaymentProvider = Depends(get_paypal_provider),
) -> ProviderConnectionResponse:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PayPal Sandbox is not configured",
        )

    try:
        token = await provider.obtain_access_token()
        access_token_encrypted = encrypt_token(token.access_token, settings.token_encryption_key)
        refresh_token_encrypted = (
            encrypt_token(token.refresh_token, settings.token_encryption_key)
            if token.refresh_token
            else None
        )
    except (PaymentProviderError, TokenEncryptionError):
        logger.exception("PayPal connect failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal could not be connected",
        ) from None

    connection = _paypal_connection(db, user.merchant_id)
    if connection is None:
        connection = ProviderConnection(
            merchant_id=user.merchant_id,
            provider="paypal",
            provider_account_id=token.provider_account_id,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            access_token_expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
            scopes=token.scopes or [],
            status="connected",
        )
        db.add(connection)
    else:
        connection.provider_account_id = token.provider_account_id
        connection.access_token_encrypted = access_token_encrypted
        connection.refresh_token_encrypted = refresh_token_encrypted
        connection.access_token_expires_at = datetime.now(UTC) + timedelta(seconds=token.expires_in)
        connection.scopes = token.scopes or []
        connection.status = "connected"
    db.commit()
    return ProviderConnectionResponse(provider="paypal", connected=True)
