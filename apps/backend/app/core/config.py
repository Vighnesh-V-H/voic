from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://voic:voic@localhost:5432/voic"
    session_cookie_name: str = "voic_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    frontend_url: str = "http://localhost:3000"
    stripe_client_id: str = ""
    stripe_platform_secret_key: str = ""
    stripe_oauth_redirect_uri: str = "http://localhost:8000/api/v1/stripe/callback"
    stripe_oauth_scope: str = "read_write"
    stripe_mode: str = "test"
    stripe_connect_webhook_secret: str = ""
    stripe_webhook_account_id: str = ""
    vobiz_auth_id: str = ""
    vobiz_auth_token: str = ""
    vobiz_caller_id: str = ""
    vobiz_answer_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator(
        "database_url",
        "session_cookie_name",
        "cors_origins",
        "frontend_url",
        "stripe_oauth_redirect_uri",
        "stripe_oauth_scope",
        "stripe_mode",
        mode="before",
    )
    @classmethod
    def use_default_when_empty(cls, value: object, info) -> object:
        """
        Replace empty or whitespace-only strings with field defaults.

        Args:
            value: The input value from environment or config.
            info: Validation info containing the field name.

        Returns:
            The default value if input is None or empty string, otherwise the original value.
        """
        if value is None:
            return cls.model_fields[info.field_name].default
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgresql_driver(cls, value: str) -> str:
        """
        Normalize PostgreSQL connection URLs to use the psycopg driver.

        Args:
            value: The database URL string.

        Returns:
            A database URL with postgresql+psycopg:// scheme if input starts with postgres:// or postgresql://.
        """
        if isinstance(value, str) and value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if isinstance(value, str) and value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """
        Parse the comma-separated cors_origins string into a list of origins.

        Returns:
            A list of non-empty origin strings.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Get the application settings singleton, cached for reuse.

    Returns:
        The application Settings instance.
    """
    return Settings()
