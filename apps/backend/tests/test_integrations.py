import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_token, encrypt_token
from app.main import app
from app.models.oauth_state import OAuthState
from app.models.provider_connection import ProviderConnection
from app.services.providers.base import OAuthToken, PaymentProvider
from app.api.integrations import get_razorpay_provider


class FakeProvider(PaymentProvider):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.exchange_calls: list[str] = []
        self.refresh_calls: list[str] = []

    async def exchange_oauth_code(self, code: str) -> OAuthToken:
        self.exchange_calls.append(code)
        return OAuthToken(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
            provider_account_id="acc_test_123",
            scopes=["read_only"],
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        self.refresh_calls.append(refresh_token)
        return OAuthToken(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=3600,
        )


@pytest.fixture
def integration_settings(client):
    settings = Settings(
        token_encryption_key=Fernet.generate_key().decode("utf-8"),
        razorpay_client_id="client-id",
        razorpay_client_secret="client-secret",
        razorpay_redirect_uri="http://localhost:8000/api/v1/integrations/razorpay/callback",
        razorpay_frontend_redirect_uri="http://localhost:3000/settings/integrations",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def fake_provider(integration_settings):
    provider = FakeProvider(integration_settings)
    app.dependency_overrides[get_razorpay_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_razorpay_provider, None)


def signup(client, email: str, merchant_name: str = "Acme"):
    return client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery", "merchant_name": merchant_name},
    )


def login(client, email: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery"},
    )


def start_connection(client) -> str:
    response = client.get("/api/v1/integrations/razorpay/connect", follow_redirects=False)
    assert response.status_code == 307
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def test_connect_generates_hashed_state_for_current_merchant(client, integration_settings):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")

    raw_state = start_connection(client)
    with app.state.testing_session_factory() as db:
        oauth_state = db.scalar(select(OAuthState))

    assert len(raw_state) >= 32
    assert oauth_state is not None
    assert oauth_state.state_hash != raw_state
    assert oauth_state.merchant_id == client.get("/api/v1/auth/me").json()["merchant"]["id"]


@pytest.mark.parametrize("query", ["code=auth-code", "code=auth-code&state=wrong-state"])
def test_callback_rejects_missing_or_invalid_state_without_exchange(client, fake_provider, query):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")

    response = client.get(f"/api/v1/integrations/razorpay/callback?{query}", follow_redirects=False)

    assert response.status_code == 303
    assert "status=oauth_state_invalid" in response.headers["location"]
    assert fake_provider.exchange_calls == []


def test_callback_rejects_reused_state(client, fake_provider):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")
    state = start_connection(client)

    first = client.get(
        f"/api/v1/integrations/razorpay/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    second = client.get(
        f"/api/v1/integrations/razorpay/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert "status=connected" in first.headers["location"]
    assert second.status_code == 303
    assert "status=oauth_state_invalid" in second.headers["location"]
    assert fake_provider.exchange_calls == ["auth-code"]


def test_callback_rejects_expired_state_without_exchange(client, fake_provider, integration_settings):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")
    state = start_connection(client)
    with app.state.testing_session_factory() as db:
        oauth_state = db.scalar(select(OAuthState))
        assert oauth_state is not None
        oauth_state.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.get(
        f"/api/v1/integrations/razorpay/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "status=oauth_state_invalid" in response.headers["location"]
    assert fake_provider.exchange_calls == []


def test_callback_without_session_returns_safe_frontend_state(client, integration_settings):
    response = client.get(
        "/api/v1/integrations/razorpay/callback?code=auth-code&state=unknown",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "status=oauth_session_invalid" in response.headers["location"]


def test_callback_persists_encrypted_connection_and_safe_status(client, fake_provider, integration_settings):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")
    state = start_connection(client)

    response = client.get(
        f"/api/v1/integrations/razorpay/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    status_response = client.get("/api/v1/integrations/razorpay/status")

    with app.state.testing_session_factory() as db:
        connection = db.scalar(select(ProviderConnection))

    assert response.status_code == 303
    assert "access-token" not in response.headers["location"]
    assert "refresh-token" not in response.headers["location"]
    assert status_response.json() == {"provider": "razorpay", "connected": True}
    assert connection is not None
    assert connection.provider_account_id == "acc_test_123"
    assert decrypt_token(connection.access_token_encrypted, integration_settings.token_encryption_key) == "access-token"
    assert decrypt_token(connection.refresh_token_encrypted, integration_settings.token_encryption_key) == "refresh-token"
    assert connection.access_token_encrypted != "access-token"
    assert connection.scopes == ["read_only"]


def test_callback_does_not_allow_a_different_merchant_to_use_state(client, fake_provider):
    signup(client, "first@example.com", "First")
    signup(client, "second@example.com", "Second")
    login(client, "first@example.com")
    state = start_connection(client)
    login(client, "second@example.com")

    response = client.get(
        f"/api/v1/integrations/razorpay/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "status=oauth_state_invalid" in response.headers["location"]
    assert fake_provider.exchange_calls == []
    assert client.get("/api/v1/integrations/razorpay/status").json() == {
        "provider": "razorpay",
        "connected": False,
    }


def test_refresh_rotates_both_encrypted_tokens(client, integration_settings):
    signup_response = signup(client, "owner@example.com")
    merchant_id = signup_response.json()["merchant"]["id"]
    provider = FakeProvider(integration_settings)
    with app.state.testing_session_factory() as db:
        connection = ProviderConnection(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_account_id="acc_test_123",
            access_token_encrypted=encrypt_token("old-access-token", integration_settings.token_encryption_key),
            refresh_token_encrypted=encrypt_token("old-refresh-token", integration_settings.token_encryption_key),
            access_token_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            scopes=["read_only"],
            status="connected",
        )
        db.add(connection)
        db.commit()
        access_token = asyncio.run(provider.get_valid_access_token(connection, db))
        db.refresh(connection)

        assert access_token == "new-access-token"
        assert provider.refresh_calls == ["old-refresh-token"]
        assert decrypt_token(connection.access_token_encrypted, integration_settings.token_encryption_key) == "new-access-token"
        assert decrypt_token(connection.refresh_token_encrypted, integration_settings.token_encryption_key) == "new-refresh-token"
