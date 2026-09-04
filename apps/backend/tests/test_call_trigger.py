import json
import time

import pytest
from sqlalchemy import select

from app.api.stripe import get_payment_provider
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import app
from app.models.call_attempt import CallAttempt
from app.models.payment import Payment
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
    "vobiz_public_base_url": "https://voic.example.com",
    "voice_callback_token": "token_test_123",
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
def db_session(client):
    override = app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    yield db
    session_generator.close()


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

    def fake_place_call(settings, *, to: str, payment_id: str, attempt_id: str) -> str:
        calls.append({"to": to, "payment_id": payment_id})
        return "call_test_123"

    monkeypatch.setattr(vobiz, "place_call", fake_place_call)
    return calls


def failed_payload_with_phone(
    payment_id: str, event_id: str = "evt_failed_call", created: int | None = None
) -> str:
    """Build a payment_intent.payment_failed payload carrying a customer phone."""
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "account": "acct_test_123",
            "created": created if created is not None else int(time.time()),
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


def post_failed_with_phone(
    client, payment_id: str, event_id: str = "evt_failed_call", created: int | None = None
):
    payload = failed_payload_with_phone(payment_id, event_id, created)
    return client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))


def test_failed_payment_with_phone_triggers_vobiz_call(client, fake_provider, vobiz_secret, recorded_calls):
    payment_id = connected_payment(client, fake_provider)

    response = post_failed_with_phone(client, payment_id)

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert recorded_calls == [{"to": CUSTOMER_PHONE, "payment_id": payment_id}]
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
    assert recorded_calls == [{"to": CUSTOMER_PHONE, "payment_id": payment_id}]


def test_distinct_failed_events_persist_one_attempt_and_call_once(
    client, fake_provider, vobiz_secret, recorded_calls, db_session
):
    payment_id = connected_payment(client, fake_provider)
    timestamp = int(time.time())

    first = post_failed_with_phone(client, payment_id, event_id="evt_failed_first", created=timestamp)
    second = post_failed_with_phone(client, payment_id, event_id="evt_failed_retry", created=timestamp + 1)

    assert first.json() == {"status": "processed"}
    assert second.json() == {"status": "processed"}
    assert recorded_calls == [{"to": CUSTOMER_PHONE, "payment_id": payment_id}]
    attempts = db_session.query(CallAttempt).filter(CallAttempt.payment_id == payment_id).all()
    assert len(attempts) == 1
    assert attempts[0].provider == "vobiz"
    assert attempts[0].provider_call_id == "call_test_123"
    assert attempts[0].status == "PLACED"
    assert attempts[0].created_at is not None
    assert attempts[0].placed_at is not None


def test_completed_payment_closes_queued_attempt_and_blocks_dial(
    client, fake_provider, vobiz_secret, recorded_calls, db_session
):
    payment_id = connected_payment(client, fake_provider)
    payment = db_session.get(Payment, payment_id)
    payment.status = "FAILED"
    attempt = CallAttempt(
        merchant_id=payment.merchant_id,
        payment_id=payment.id,
        provider="vobiz",
        status="QUEUED",
    )
    db_session.add(attempt)
    db_session.commit()

    payload = checkout_completed_payload(payment_id, event_id="evt_recovered_payment")
    response = client.post("/api/v1/webhooks/stripe", content=payload, headers=signed_headers(payload))

    assert response.json() == {"status": "processed"}
    db_session.refresh(attempt)
    assert attempt.status == "CANCELLED"
    assert attempt.closed_at is not None
    assert recorded_calls == []


def test_out_of_order_failure_after_success_does_not_dial(
    client, fake_provider, vobiz_secret, recorded_calls, db_session
):
    payment_id = connected_payment(client, fake_provider)
    success_time = int(time.time()) + 10
    success = checkout_completed_payload(payment_id, event_id="evt_success_first", created=success_time)
    failure = failed_payload_with_phone(payment_id, event_id="evt_failure_late_delivery", created=success_time - 1)

    assert client.post("/api/v1/webhooks/stripe", content=success, headers=signed_headers(success)).json() == {
        "status": "processed"
    }
    assert client.post("/api/v1/webhooks/stripe", content=failure, headers=signed_headers(failure)).json() == {
        "status": "processed"
    }
    assert client.get(f"/api/v1/payments/{payment_id}").json()["status"] == "COMPLETED"
    assert db_session.query(CallAttempt).filter(CallAttempt.payment_id == payment_id).count() == 0


def test_attempt_requires_the_payment_merchant_boundary(
    client, fake_provider, vobiz_secret, recorded_calls, db_session
):
    payment_id = connected_payment(client, fake_provider)
    payment = db_session.get(Payment, payment_id)
    payment.status = "FAILED"
    db_session.commit()

    result = trigger_recovery_call(
        Settings(**VOBIZ_SETTINGS),
        event_type="payment_intent.payment_failed",
        merchant_id="another-merchant",
        payment_id=payment_id,
        customer_phone=CUSTOMER_PHONE,
        db=db_session,
    )

    assert result == "skipped:payment-not-found"
    assert recorded_calls == []
    assert db_session.query(CallAttempt).filter(CallAttempt.payment_id == payment_id).count() == 0


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


def test_trigger_surfaces_provider_error_as_skip(client, fake_provider, vobiz_secret, monkeypatch):
    def boom(settings, *, to: str, payment_id: str, attempt_id: str) -> str:
        raise VobizCallError("down")

    monkeypatch.setattr(vobiz, "place_call", boom)
    payment_id = connected_payment(client, fake_provider)
    override = app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)

    try:
        payment = db.scalar(select(Payment).where(Payment.id == payment_id))
        merchant_id = payment.merchant_id
        payment.status = "FAILED"
        db.commit()
        assert (
            trigger_recovery_call(
                Settings(**VOBIZ_SETTINGS),
                event_type="payment_intent.payment_failed",
                merchant_id=merchant_id,
                payment_id=payment_id,
                customer_phone=CUSTOMER_PHONE,
                db=db,
            )
            == "skipped:vobiz-error"
        )
    finally:
        session_generator.close()
