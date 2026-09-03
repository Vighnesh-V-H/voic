from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://voic:voic@localhost:5432/voic"
    session_cookie_name: str = "voic_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    token_encryption_key: str = ""
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_api_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_frontend_return_url: str = "http://localhost:3000/payments/paypal/return"
    paypal_frontend_cancel_url: str = "http://localhost:3000/payments/paypal/return?cancelled=1"
    paypal_http_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def drop_empty_values(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if not (isinstance(v, str) and v.strip() == "")}
        return values

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
