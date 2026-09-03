from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.crypto import TokenEncryptionError, decrypt_token, encrypt_token
from app.models.provider_connection import ProviderConnection


class PaymentProviderError(Exception):
    """An expected provider failure safe to expose as a generic payment error."""


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    expires_in: int
    refresh_token: str | None = None
    provider_account_id: str | None = None
    scopes: list[str] | None = None


@dataclass(frozen=True)
class PaymentOrder:
    order_id: str
    status: str
    approval_url: str | None


@dataclass(frozen=True)
class PaymentCapture:
    status: str
    capture_id: str | None


class PaymentProvider(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    async def obtain_access_token(self) -> OAuthToken:
        raise NotImplementedError

    @abstractmethod
    async def create_payment(
        self, access_token: str, amount: str, currency: str, request_id: str
    ) -> PaymentOrder:
        raise NotImplementedError

    @abstractmethod
    async def capture_payment(self, access_token: str, order_id: str) -> PaymentCapture:
        raise NotImplementedError

    @abstractmethod
    async def get_payment_status(self, access_token: str, order_id: str) -> PaymentCapture:
        raise NotImplementedError

    async def get_valid_access_token(self, connection: ProviderConnection, db: Session) -> str:
        now = datetime.now(UTC)
        expires_at = connection.access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at > now + timedelta(seconds=60):
            return self._decrypt_access_token(connection)

        # Recheck under a row lock so concurrent workers do not all refresh the token.
        locked_connection = db.scalar(
            select(ProviderConnection)
            .where(ProviderConnection.id == connection.id)
            .with_for_update()
        )
        if locked_connection is None:
            raise PaymentProviderError("Provider connection is unavailable")
        connection = locked_connection
        expires_at = connection.access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > now + timedelta(seconds=60):
            return self._decrypt_access_token(connection)

        token = await self.obtain_access_token()
        try:
            connection.access_token_encrypted = encrypt_token(
                token.access_token, self.settings.token_encryption_key
            )
            if token.refresh_token:
                connection.refresh_token_encrypted = encrypt_token(
                    token.refresh_token, self.settings.token_encryption_key
                )
        except TokenEncryptionError as error:
            raise PaymentProviderError("Token encryption is not configured") from error

        connection.access_token_expires_at = now + timedelta(seconds=token.expires_in)
        if token.scopes:
            connection.scopes = token.scopes
        db.commit()
        return token.access_token

    def _decrypt_access_token(self, connection: ProviderConnection) -> str:
        try:
            return decrypt_token(connection.access_token_encrypted, self.settings.token_encryption_key)
        except TokenEncryptionError as error:
            raise PaymentProviderError("Stored provider credentials are unavailable") from error
