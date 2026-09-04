import json
import time

import pytest

from app.api.stripe import get_payment_provider
from app.core.config import Settings, get_settings
from app.main import app
from app.services.calls import vobiz
from app.services.calls.vobiz import VobizCallError, trigger_recovery_call
from tests.test_stripe import (
    WEBHOOK_SECRET,
    FakeStripeProvider,
    checkout_completed_payload,
    connected_payment,
    signed_headers,
    webhook_payload,
)

VOBIZ_SETTINGS = {
    "vobiz_auth_id": "auth_test_id",
    "vobiz_auth_token": "auth_test_token",
    "vobiz_caller_id": "+911234567890",
    "vobiz_answer_url": "https://voic.example.com/voice/answer",
}
CUSTOMER_PHONE = "+919876543210"


@pytest.fixture()
def vobiz_secret():
    app.dependency_overrides[get_settings] = lambda: Settings(
        stripe_connect_webhook_secret=WEBHOOK_SECRET, **VOBIZ_SETTINGS
    )
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def plain_secret():
    app.dependency_overrides[get_settings] = lambda: Settings(
        stripe_connect_webhook_secret=WEBHOOK_SECRET
    )
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def fake_provider():
    provider = FakeStripeProvider()
    app.dependency_overrides[get_payment_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_payment_provider, None)


@pytest.fixture()
def recorded_calls(monkeypatch):
    calls: list[dict] = []

    def fake_place_call(settings, *, to: str) -> str:
        calls.append({"to": to})
        return "call_test_123"

    monkeypatch.setattr(vobiz, "place_call", fake_place_call)
    return calls


def failed_payload_with_phone(payment_id: str, event_id: str = "evt_failed_call") -> str:
    """Build a payment_intent.payment_failed payload carrying a customer phone."""
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "account": "acct_test_123",
            "created": int(time.time()),
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "amount": 2500,
                    "currency": "usd",
                    "customer_details": {"phone": CUSTOMER_PHONE},
                    "metadata": {"voic_payment_id": payment_id},
                }
            },
        },
        separators=(",", ":"),
    )


def post_failed_with_phone(client, payment_id: str, event_id: str = "evt_failed_call"):
    payload = failed_payload_with_phone(payment_id, event_id)
    return client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))


def test_failed_payment_with_phone_triggers_vobiz_call(client, fake_provider, vobiz_secret, recorded_calls):
    payment_id = connected_payment(client, fake_provider)

    response = post_failed_with_phone(client, payment_id)

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert recorded_calls == [{"to": CUSTOMER_PHONE}]
    assert client.get(f"/api/v1/payments/{payment_id}").json()["status"] == "FAILED"


def test_failed_payment_without_phone_skips_call(client, fake_provider, vobiz_secret, recorded_calls):
    payment_id = connected_payment(client, fake_provider)
    payload = webhook_payload(payment_id)

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert recorded_calls == []


def test_failed_payment_without_vobiz_config_skips_call(
    client, fake_provider, plain_secret, monkeypatch
):
    def fail_if_called(settings, *, to: str) -> str:
        raise AssertionError("place_call must not run without Vobiz config")

    monkeypatch.setattr(vobiz, "place_call", fail_if_called)
    payment_id = connected_payment(client, fake_provider)

    response = post_failed_with_phone(client, payment_id)

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}


def test_success_event_does_not_trigger_call(client, fake_provider, vobiz_secret, recorded_calls):
    payment_id = connected_payment(client, fake_provider)
    payload = checkout_completed_payload(payment_id)

    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.status_code == 200
    assert recorded_calls == []


def test_duplicate_failed_event_calls_only_once(client, fake_provider, vobiz_secret, recorded_calls):
    payment_id = connected_payment(client, fake_provider)

    first = post_failed_with_phone(client, payment_id, event_id="evt_failed_once")
    second = post_failed_with_phone(client, payment_id, event_id="evt_failed_once")

    assert first.json() == {"status": "processed"}
    assert second.json() == {"status": "duplicate"}
    assert recorded_calls == [{"to": CUSTOMER_PHONE}]


def test_trigger_rejects_non_trigger_event():
    settings = Settings(**VOBIZ_SETTINGS)

    assert (
        trigger_recovery_call(
            settings,
            event_type="checkout.session.completed",
            merchant_id="m_1",
            payment_id="pay_1",
            customer_phone=CUSTOMER_PHONE,
        )
        == "skipped:event-not-trigger"
    )


def test_trigger_skips_when_vobiz_unconfigured():
    assert (
        trigger_recovery_call(
            Settings(),
            event_type="payment_intent.payment_failed",
            merchant_id="m_1",
            payment_id="pay_1",
            customer_phone=CUSTOMER_PHONE,
        )
        == "skipped:vobiz-not-configured"
    )


def test_trigger_surfaces_provider_error_as_skip(monkeypatch):
    def boom(settings, *, to: str) -> str:
        raise VobizCallError("down")

    monkeypatch.setattr(vobiz, "place_call", boom)

    assert (
        trigger_recovery_call(
            Settings(**VOBIZ_SETTINGS),
            event_type="payment_intent.payment_failed",
            merchant_id="m_1",
            payment_id="pay_1",
            customer_phone=CUSTOMER_PHONE,
        )
        == "skipped:vobiz-error"
    )
