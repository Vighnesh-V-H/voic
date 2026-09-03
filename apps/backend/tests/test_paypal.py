from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.api.integrations import get_paypal_provider
from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_token
from app.main import app
from app.models.payment_transaction import PaymentTransaction
from app.models.provider_connection import ProviderConnection
from app.services.providers.base import (
    OAuthToken,
    PaymentCapture,
    PaymentOrder,
    PaymentProvider,
    PaymentProviderError,
)


class FakePayPalProvider(PaymentProvider):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.fail_capture = False
        self.created_orders: list[tuple[str, str]] = []

    async def obtain_access_token(self) -> OAuthToken:
        return OAuthToken(
            access_token="paypal-access-token",
            expires_in=3600,
            provider_account_id="app-sandbox-id",
            scopes=["openid"],
        )

    async def create_payment(
        self, access_token: str, amount: str, currency: str, request_id: str
    ) -> PaymentOrder:
        self.created_orders.append((amount, currency))
        return PaymentOrder("ORDER-123", "CREATED", "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123")

    async def capture_payment(self, access_token: str, order_id: str) -> PaymentCapture:
        if self.fail_capture:
            raise PaymentProviderError("simulated provider failure")
        return PaymentCapture("COMPLETED", "CAPTURE-123")

    async def get_payment_status(self, access_token: str, order_id: str) -> PaymentCapture:
        return PaymentCapture("CREATED", None)


@pytest.fixture
def paypal_settings(client):
    settings = Settings(
        token_encryption_key=Fernet.generate_key().decode("utf-8"),
        paypal_client_id="client-id",
        paypal_client_secret="client-secret",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def paypal_provider(paypal_settings):
    provider = FakePayPalProvider(paypal_settings)
    app.dependency_overrides[get_paypal_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_paypal_provider, None)


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


def connect(client):
    signup(client, "owner@example.com")
    login(client, "owner@example.com")
    return client.post("/api/v1/integrations/paypal/connect")


def test_paypal_connection_stores_only_encrypted_token_and_safe_status(
    client, paypal_provider, paypal_settings
):
    response = connect(client)
    status_response = client.get("/api/v1/integrations/paypal/status")

    with app.state.testing_session_factory() as db:
        connection = db.scalar(select(ProviderConnection))

    assert response.status_code == 200
    assert response.json() == {"provider": "paypal", "connected": True}
    assert status_response.json() == {"provider": "paypal", "connected": True}
    assert connection is not None
    assert decrypt_token(connection.access_token_encrypted, paypal_settings.token_encryption_key) == "paypal-access-token"
    assert "paypal-access-token" not in response.text


def test_payment_creation_and_capture_are_reported_to_backend(client, paypal_provider):
    connect(client)

    order_response = client.post(
        "/api/v1/payments/paypal/orders",
        json={"amount": "12.50", "currency": "USD"},
    )
    order = order_response.json()
    capture_response = client.post(f"/api/v1/payments/paypal/orders/{order['order_id']}/capture")
    status_response = client.get(f"/api/v1/payments/paypal/orders/{order['order_id']}")

    assert order_response.status_code == 201
    assert order == {
        "order_id": "ORDER-123",
        "status": "CREATED",
        "approval_url": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123",
        "amount": "12.50",
        "currency": "USD",
    }
    assert capture_response.status_code == 200
    assert capture_response.json()["status"] == "COMPLETED"
    assert capture_response.json()["capture_id"] == "CAPTURE-123"
    assert status_response.json()["status"] == "COMPLETED"
    assert paypal_provider.created_orders == [("12.50", "USD")]


def test_payment_failure_is_persisted_safely(client, paypal_provider):
    connect(client)
    order_response = client.post(
        "/api/v1/payments/paypal/orders",
        json={"amount": "1.00", "currency": "USD"},
    )
    paypal_provider.fail_capture = True

    response = client.post(f"/api/v1/payments/paypal/orders/{order_response.json()['order_id']}/capture")

    with app.state.testing_session_factory() as db:
        transaction = db.scalar(select(PaymentTransaction))

    assert response.status_code == 502
    assert response.json() == {"detail": "PayPal could not complete the payment"}
    assert transaction is not None
    assert transaction.status == "UNKNOWN"
    assert "simulated" not in response.text


def test_cancelled_payment_cannot_be_captured(client, paypal_provider):
    connect(client)
    order_response = client.post(
        "/api/v1/payments/paypal/orders",
        json={"amount": "2.00", "currency": "USD"},
    )
    order_id = order_response.json()["order_id"]
    cancel_response = client.post(f"/api/v1/payments/paypal/orders/{order_id}/cancel")
    capture_response = client.post(f"/api/v1/payments/paypal/orders/{order_id}/capture")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"
    assert capture_response.status_code == 409


def test_payments_are_tenant_scoped(client, paypal_provider):
    connect(client)
    order_response = client.post(
        "/api/v1/payments/paypal/orders",
        json={"amount": "4.00", "currency": "USD"},
    )
    order_id = order_response.json()["order_id"]
    signup(client, "second@example.com", "Second")
    login(client, "second@example.com")

    response = client.get(f"/api/v1/payments/paypal/orders/{order_id}")

    assert response.status_code == 404


def test_expired_paypal_token_is_replaced(client, paypal_settings, paypal_provider):
    signup_response = signup(client, "owner@example.com")
    merchant_id = signup_response.json()["merchant"]["id"]
    with app.state.testing_session_factory() as db:
        connection = ProviderConnection(
            merchant_id=merchant_id,
            provider="paypal",
            provider_account_id="app-sandbox-id",
            access_token_encrypted="invalid-old-token",
            refresh_token_encrypted=None,
            access_token_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            scopes=[],
            status="connected",
        )
        db.add(connection)
        db.commit()

        # The provider obtains a fresh client-credentials token when the old one expires.
        from asyncio import run

        access_token = run(paypal_provider.get_valid_access_token(connection, db))

    assert access_token == "paypal-access-token"
