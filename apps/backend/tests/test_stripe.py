import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.api.stripe import get_payment_provider, state_digest
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import app
from app.models.oauth_state import OAuthState


class FakeStripeProvider:
    def __init__(self):
        self.exchange_calls: list[str] = []
        self.deauthorize_calls: list[str] = []
        self.product_calls: list[str] = []
        self.price_list_calls: list[str] = []
        self.price_calls: list[tuple[str, str]] = []
        self.payment_intent_calls: list[tuple[str, int, str, dict[str, str]]] = []
        self.payment_link_calls: list[tuple[str, str, int, dict[str, str]]] = []
        self.livemode = False
        self.account_id = "acct_test_123"

    def authorization_url(self, state: str) -> str:
        return f"https://stripe.example/authorize?state={state}"

    def exchange_oauth_code(self, code: str) -> dict[str, str]:
        self.exchange_calls.append(code)
        return {
            "stripe_user_id": self.account_id,
            "scope": "read_write",
            "livemode": self.livemode,
            "access_token": "should-not-be-stored",
            "refresh_token": "should-not-be-stored",
        }

    def deauthorize(self, account_id: str) -> None:
        self.deauthorize_calls.append(account_id)

    def list_products(self, account_id: str):
        self.product_calls.append(account_id)
        return [{"id": "prod_123", "name": "Consulting", "description": "Advice", "active": True}]

    def get_price(self, account_id: str, price_id: str):
        self.price_calls.append((account_id, price_id))
        return {"id": price_id, "type": "one_time", "unit_amount": 2500, "currency": "usd"}

    def list_prices(self, account_id: str):
        self.price_list_calls.append(account_id)
        return [
            {
                "id": "price_123",
                "product": "prod_123",
                "type": "one_time",
                "unit_amount": 2500,
                "currency": "usd",
                "active": True,
            }
        ]

    def create_payment_intent(self, account_id: str, amount: int, currency: str, metadata, idempotency_key: str):
        self.payment_intent_calls.append((account_id, amount, currency, dict(metadata)))
        return {"id": "pi_test_123", "client_secret": "pi_secret_123"}

    def create_payment_link(self, account_id: str, price_id: str, quantity: int, metadata, idempotency_key: str):
        self.payment_link_calls.append((account_id, price_id, quantity, dict(metadata)))
        return {
            "id": "plink_test_123",
            "url": "https://buy.stripe.com/test_link",
            "currency": "usd",
            "amount": 2500 * quantity,
            "metadata": dict(metadata),
        }


WEBHOOK_SECRET = "whsec_test"


@pytest.fixture()
def webhook_secret():
    app.dependency_overrides[get_settings] = lambda: Settings(stripe_connect_webhook_secret=WEBHOOK_SECRET)
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def fake_provider():
    provider = FakeStripeProvider()
    app.dependency_overrides[get_payment_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_payment_provider, None)


def signup_and_login(client, email: str, merchant_name: str):
    """
    Create a new merchant account and log in to establish a session.

    Args:
        client: The test client for making HTTP requests.
        email: The email address for the new account.
        merchant_name: The merchant name for the new account.

    Returns:
        The login response object.
    """
    client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery", "merchant_name": merchant_name},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery"},
    )


def connect_state(client) -> str:
    """
    Initiate a Stripe OAuth connection and extract the state parameter.

    Args:
        client: The test client for making HTTP requests.

    Returns:
        The OAuth state token from the authorization URL.
    """
    response = client.get("/api/v1/stripe/connect", follow_redirects=False)
    assert response.status_code == 307
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def test_connect_starts_oauth_for_authenticated_merchant(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")

    response = client.get("/api/v1/stripe/connect", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://stripe.example/authorize")
    assert parse_qs(urlparse(response.headers["location"]).query)["state"]


def test_callback_stores_safe_connection_and_status(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)

    callback = client.get(
        f"/api/v1/stripe/callback?code=oauth-code&state={state}",
        follow_redirects=False,
    )

    assert callback.status_code == 307
    assert fake_provider.exchange_calls == ["oauth-code"]
    connection = client.get("/api/v1/stripe/connection")
    assert connection.status_code == 200
    assert connection.json() == {
        "provider": "stripe",
        "connected": True,
        "provider_account_id": "acct_test_123",
        "scope": "read_write",
        "mode": "test",
        "status": "connected",
    }
    assert "should-not-be-stored" not in connection.text


def test_callback_rejects_invalid_state_before_exchange(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")

    response = client.get(
        "/api/v1/stripe/callback?code=oauth-code&state=not-valid",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OAUTH_STATE_MISMATCH"
    assert fake_provider.exchange_calls == []


def expire_oauth_state(state: str) -> None:
    """
    Manually expire an OAuth state record in the database for testing.

    Args:
        state: The raw OAuth state token to expire.
    """
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        row = db.scalar(select(OAuthState).where(OAuthState.state_hash == state_digest(state)))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        gen.close()


def test_callback_rejects_expired_state_before_exchange(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    expire_oauth_state(state)

    response = client.get(
        f"/api/v1/stripe/callback?code=oauth-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OAUTH_STATE_MISMATCH"
    assert fake_provider.exchange_calls == []


def test_callback_state_is_bound_to_merchant(client, fake_provider):
    signup_and_login(client, "first@example.com", "First Merchant")
    first_state = connect_state(client)

    signup_and_login(client, "second@example.com", "Second Merchant")

    response = client.get(
        f"/api/v1/stripe/callback?code=oauth-code&state={first_state}",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OAUTH_STATE_MISMATCH"
    assert fake_provider.exchange_calls == []


def test_connect_requires_authentication(client, fake_provider):
    response = client.get("/api/v1/stripe/connect", follow_redirects=False)

    assert response.status_code == 401


def test_callback_state_is_single_use(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)

    first = client.get(
        f"/api/v1/stripe/callback?code=first&state={state}",
        follow_redirects=False,
    )
    second = client.get(
        f"/api/v1/stripe/callback?code=second&state={state}",
        follow_redirects=False,
    )

    assert first.status_code == 307
    assert second.status_code == 400
    assert second.json()["detail"] == "OAUTH_STATE_MISMATCH"
    assert fake_provider.exchange_calls == ["first"]


def test_callback_rejects_live_account_during_test_mode(client, fake_provider):
    fake_provider.livemode = True
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)

    response = client.get(
        f"/api/v1/stripe/callback?code=oauth-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "STRIPE_MODE_MISMATCH"


def test_reconnect_updates_existing_provider_connection(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    first_state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=first&state={first_state}", follow_redirects=False)
    second_state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=second&state={second_state}", follow_redirects=False)

    assert client.get("/api/v1/stripe/connection").json()["provider_account_id"] == "acct_test_123"


def test_reconnect_preserves_old_account_payment_history(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    fake_provider.account_id = "acct_test_456"
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=second&state={state}", follow_redirects=False)
    payload = webhook_payload(payment_id, account_id="acct_test_123", event_id="evt_old_account")

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert client.get(f"/api/v1/payments/{payment_id}").json()["status"] == "COMPLETED"
    assert client.get("/api/v1/stripe/connection").json()["provider_account_id"] == "acct_test_456"


def test_same_stripe_account_cannot_be_connected_to_two_merchants(client, fake_provider):
    signup_and_login(client, "first@example.com", "First Merchant")
    first_state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=first&state={first_state}", follow_redirects=False)
    signup_and_login(client, "second@example.com", "Second Merchant")
    second_state = connect_state(client)

    response = client.get(
        f"/api/v1/stripe/callback?code=second&state={second_state}",
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "STRIPE_ACCOUNT_ALREADY_CONNECTED"


def test_disconnect_deauthorizes_and_preserves_connection_record(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)

    response = client.delete("/api/v1/stripe/connection")

    assert response.status_code == 204
    assert fake_provider.deauthorize_calls == ["acct_test_123"]
    connection = client.get("/api/v1/stripe/connection").json()
    assert connection["connected"] is False
    assert connection["status"] == "disconnected"


def test_connection_is_scoped_to_authenticated_merchant(client, fake_provider):
    signup_and_login(client, "first@example.com", "First Merchant")
    first_state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=first&state={first_state}", follow_redirects=False)

    signup_and_login(client, "second@example.com", "Second Merchant")

    assert client.get("/api/v1/stripe/connection").json()["connected"] is False


def test_products_are_read_from_connected_stripe_account(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)

    response = client.get("/api/v1/stripe/products")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "prod_123", "name": "Consulting", "description": "Advice", "active": True, "default_price": None}
    ]
    assert fake_provider.product_calls == ["acct_test_123"]


def test_prices_are_read_from_connected_stripe_account(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)

    response = client.get("/api/v1/stripe/prices")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "price_123",
            "product_id": "prod_123",
            "unit_amount": 2500,
            "currency": "usd",
            "active": True,
            "type": "one_time",
        }
    ]
    assert fake_provider.price_list_calls == ["acct_test_123"]


def test_payment_uses_existing_price_and_returns_client_secret(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)

    response = client.post("/api/v1/payments", json={"price_id": "price_123", "quantity": 2})

    assert response.status_code == 201
    body = response.json()
    assert body["provider_payment_id"] == "pi_test_123"
    assert body["amount"] == 5000
    assert body["currency"] == "usd"
    assert body["status"] == "PENDING"
    assert body["client_secret"] == "pi_secret_123"
    assert fake_provider.payment_intent_calls[0][0:3] == ("acct_test_123", 5000, "usd")
    assert fake_provider.payment_intent_calls[0][3]["voic_payment_id"] == body["id"]
    assert client.get(f"/api/v1/payments/{body['id']}").json()["client_secret"] is None


def test_payment_requires_a_connected_account(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")

    response = client.post("/api/v1/payments", json={"price_id": "price_123"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Stripe connection required"


def test_payment_request_idempotency_reuses_existing_payment(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)
    headers = {"Idempotency-Key": "checkout-123"}

    first = client.post("/api/v1/payments", json={"price_id": "price_123"}, headers=headers)
    second = client.post("/api/v1/payments", json={"price_id": "price_123"}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert len(fake_provider.payment_intent_calls) == 1


def test_payment_link_uses_existing_price_and_returns_hosted_url(client, fake_provider):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)

    response = client.post("/api/v1/payment-links", json={"price_id": "price_123", "quantity": 2})

    assert response.status_code == 201
    body = response.json()
    assert body["provider_payment_link_id"] == "plink_test_123"
    assert body["url"] == "https://buy.stripe.com/test_link"
    assert body["amount"] == 5000
    assert body["status"] == "PENDING"
    assert fake_provider.payment_link_calls[0][0:3] == ("acct_test_123", "price_123", 2)
    assert fake_provider.payment_link_calls[0][3]["voic_payment_id"] == body["id"]
    assert client.get(f"/api/v1/payment-links/{body['id']}").json()["url"] == "https://buy.stripe.com/test_link"


def signed_headers(payload: str) -> dict[str, str]:
    """
    Generate a valid Stripe webhook signature header for the given payload.

    Args:
        payload: The webhook payload string.

    Returns:
        A dictionary with the Stripe-Signature header.
    """
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload}".encode()
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={signature}"}


def connected_payment(client, fake_provider) -> str:
    """
    Create a merchant, connect Stripe, and create a payment for testing webhooks.

    Args:
        client: The test client for making HTTP requests.
        fake_provider: The fake Stripe provider fixture.

    Returns:
        The payment ID of the created payment.
    """
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)
    return client.post("/api/v1/payments", json={"price_id": "price_123"}).json()["id"]


def webhook_payload(
    payment_id: str,
    event_type: str = "payment_intent.succeeded",
    account_id: str = "acct_test_123",
    event_id: str | None = None,
) -> str:
    """
    Generate a fake Stripe webhook event payload for testing.

    Args:
        payment_id: The Voic payment ID to include in metadata.
        event_type: The Stripe event type (e.g., payment_intent.succeeded).
        account_id: The Stripe account ID for the event.
        event_id: Optional event ID (generated if not provided).

    Returns:
        A JSON-encoded webhook event payload string.
    """
    return json.dumps(
        {
            "id": event_id or ("evt_test_123" if event_type.endswith("succeeded") else "evt_test_failed"),
            "object": "event",
            "account": account_id,
            "created": int(time.time()),
            "type": event_type,
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "amount": 2500,
                    "currency": "usd",
                    "metadata": {"voic_payment_id": payment_id},
                }
            },
        },
        separators=(",", ":"),
    )


def test_valid_webhook_persists_event_and_completes_payment(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    payload = webhook_payload(payment_id)

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    payment = client.get(f"/api/v1/payments/{payment_id}").json()
    assert payment["status"] == "COMPLETED"
    events = client.get("/api/v1/webhooks/payment-events")
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "payment_intent.succeeded"
    assert "raw_payload" not in events.json()[0]


def test_failed_webhook_updates_payment_status(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    payload = webhook_payload(payment_id, "payment_intent.payment_failed")

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert client.get(f"/api/v1/payments/{payment_id}").json()["status"] == "FAILED"


def test_late_failure_does_not_downgrade_completed_payment(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    succeeded_payload = webhook_payload(payment_id)
    failed_payload = webhook_payload(payment_id, "payment_intent.payment_failed")

    client.post("/api/v1/webhooks/stripe", content=succeeded_payload, headers=signed_headers(succeeded_payload))
    client.post("/api/v1/webhooks/stripe", content=failed_payload, headers=signed_headers(failed_payload))

    assert client.get(f"/api/v1/payments/{payment_id}").json()["status"] == "COMPLETED"


def test_deauthorization_disconnects_known_provider_connection(client, fake_provider, webhook_secret):
    signup_and_login(client, "owner@example.com", "Acme Store")
    state = connect_state(client)
    client.get(f"/api/v1/stripe/callback?code=oauth-code&state={state}", follow_redirects=False)
    payment_id = client.post("/api/v1/payments", json={"price_id": "price_123"}).json()["id"]
    payload = webhook_payload("not-a-payment", "account.application.deauthorized")

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert client.get("/api/v1/stripe/connection").json()["status"] == "disconnected"
    assert client.get(f"/api/v1/payments/{payment_id}").status_code == 200


def test_payments_and_events_are_scoped_to_the_current_merchant(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    payload = webhook_payload(payment_id)
    client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))
    signup_and_login(client, "second@example.com", "Second Merchant")

    assert client.get(f"/api/v1/payments/{payment_id}").status_code == 404
    assert client.get("/api/v1/webhooks/payment-events").json() == []


def test_webhook_rejects_invalid_signature(client, fake_provider, webhook_secret):
    payload = webhook_payload("payment-id")

    response = client.post(
        "/api/v1/webhooks/stripe", content=payload, headers={"Stripe-Signature": "t=1,v1=invalid"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "WEBHOOK_INVALID_SIGNATURE"


def test_duplicate_webhook_is_ignored(client, fake_provider, webhook_secret):
    payment_id = connected_payment(client, fake_provider)
    payload = webhook_payload(payment_id)
    headers = signed_headers(payload)

    first = client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)
    second = client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)

    assert first.json() == {"status": "processed"}
    assert second.json() == {"status": "duplicate"}


def test_webhook_rejects_unknown_connected_account(client, fake_provider, webhook_secret):
    payload = json.loads(webhook_payload("payment-id"))
    payload["account"] = "acct_unknown"
    payload = json.dumps(payload, separators=(",", ":"))

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "WEBHOOK_UNKNOWN_MERCHANT"


def test_webhook_rejects_malformed_payload(client, fake_provider, webhook_secret):
    payload = "not-json"

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "WEBHOOK_INVALID_PAYLOAD"
