from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://voic:voic@localhost:5432/voic"
    session_cookie_name: str = "voic_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    token_encryption_key: str = ""
    razorpay_client_id: str = ""
    razorpay_client_secret: str = ""
    razorpay_redirect_uri: str = "http://localhost:8000/api/v1/integrations/razorpay/callback"
    razorpay_frontend_redirect_uri: str = "http://localhost:3000/settings/integrations"
    razorpay_authorize_url: str = "https://auth.razorpay.com/authorize"
    razorpay_token_url: str = "https://auth.razorpay.com/token"
    razorpay_scope: str = "read_only"
    razorpay_mode: str = "test"
    oauth_state_ttl_seconds: int = 10 * 60
    oauth_http_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgresql_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
