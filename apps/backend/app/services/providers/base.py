from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.crypto import TokenEncryptionError, decrypt_token, encrypt_token
from app.models.provider_connection import ProviderConnection


class ProviderError(Exception):
    """An expected provider failure safe to expose as a generic integration error."""


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    refresh_token: str | None
    expires_in: int
    provider_account_id: str | None = None
    scopes: list[str] | None = None


class PaymentProvider(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    async def exchange_oauth_code(self, code: str) -> OAuthToken:
        raise NotImplementedError

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        raise NotImplementedError

    async def get_valid_access_token(self, connection: ProviderConnection, db: Session) -> str:
        now = datetime.now(UTC)
        expires_at = connection.access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at > now + timedelta(seconds=60):
            try:
                return decrypt_token(connection.access_token_encrypted, self.settings.token_encryption_key)
            except TokenEncryptionError as error:
                raise ProviderError("Stored provider credentials are unavailable") from error

        # Lock and reload before rotating so only one worker can spend a refresh token.
        locked_connection = db.scalar(
            select(ProviderConnection)
            .where(ProviderConnection.id == connection.id)
            .with_for_update()
        )
        if locked_connection is None:
            raise ProviderError("Provider connection is unavailable")
        connection = locked_connection
        expires_at = connection.access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > now + timedelta(seconds=60):
            try:
                return decrypt_token(connection.access_token_encrypted, self.settings.token_encryption_key)
            except TokenEncryptionError as error:
                raise ProviderError("Stored provider credentials are unavailable") from error

        try:
            refresh_token = decrypt_token(
                connection.refresh_token_encrypted, self.settings.token_encryption_key
            )
        except TokenEncryptionError as error:
            raise ProviderError("Stored provider credentials are unavailable") from error

        token = await self.refresh_access_token(refresh_token)
        if not token.refresh_token:
            raise ProviderError("Provider did not return a refresh token")

        try:
            connection.access_token_encrypted = encrypt_token(
                token.access_token, self.settings.token_encryption_key
            )
            connection.refresh_token_encrypted = encrypt_token(
                token.refresh_token, self.settings.token_encryption_key
            )
        except TokenEncryptionError as error:
            raise ProviderError("Token encryption is not configured") from error

        connection.access_token_expires_at = now + timedelta(seconds=token.expires_in)
        db.commit()
        return token.access_token
