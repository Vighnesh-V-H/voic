import io
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base
from app.models.call_attempt import CallAttempt
from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.provider_connection import ProviderConnection
from app.services.agent import resend
from app.services.agent import tools as agent_tools
from app.services.agent.resend import ResendEmailError
from app.services.agent.tools import ToolError

RESEND_SETTINGS = {
    "resend_api_key": "re_test_123",
    "resend_from_email": "Voic <onboarding@resend.dev>",
}
CUSTOMER_EMAIL = "customer@example.com"
CONVERSATION_ID = "conv_test_123"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestingSessionLocal() as session:
        merchant = Merchant(name="Test Merchant")
        session.add(merchant)
        session.flush()
        connection = ProviderConnection(
            merchant_id=merchant.id,
            provider="stripe",
            provider_account_id="acct_test_123",
            mode="test",
            scope="read_write",
            status="connected",
        )
        session.add(connection)
        session.flush()
        payment = Payment(
            merchant_id=merchant.id,
            provider_connection_id=connection.id,
            provider="stripe",
            provider_account_id="acct_test_123",
            provider_payment_id="pi_test_123",
            provider_price_id="price_test_123",
            amount=2500,
            currency="usd",
            status="FAILED",
        )
        session.add(payment)
        session.flush()
        session.add(
            PaymentEvent(
                merchant_id=merchant.id,
                provider_connection_id=connection.id,
                provider="stripe",
                provider_event_id="evt_test_123",
                event_type="payment_intent.payment_failed",
                provider_payment_id="pi_test_123",
                customer_email=CUSTOMER_EMAIL,
                raw_payload="{}",
                occurred_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            CallAttempt(
                merchant_id=merchant.id,
                payment_id=payment.id,
                provider="vobiz",
                status="BRIDGED",
                elevenlabs_conversation_id=CONVERSATION_ID,
            )
        )
        session.commit()
        yield session, payment
    Base.metadata.drop_all(engine)


def test_resend_is_configured_requires_key_and_from():
    assert resend.is_configured(Settings(_env_file=None)) is False
    assert resend.is_configured(Settings(_env_file=None, resend_api_key="key")) is False
    assert resend.is_configured(Settings(_env_file=None, resend_from_email="a@b.com")) is False
    assert resend.is_configured(Settings(_env_file=None, **RESEND_SETTINGS)) is True


def test_resend_client_builds_request_and_returns_id(monkeypatch):
    captured = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(b'{"id": "msg_test_123"}')

    monkeypatch.setattr(resend.urllib.request, "urlopen", fake_urlopen)
    settings = Settings(_env_file=None, **RESEND_SETTINGS)

    message_id = resend.send_email(settings, CUSTOMER_EMAIL, "Payment reminder", "Hello")

    assert message_id == "msg_test_123"
    assert captured["url"] == resend.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer re_test_123"
    assert captured["body"]["to"] == [CUSTOMER_EMAIL]
    assert captured["body"]["from"] == "Voic <onboarding@resend.dev>"
    assert captured["body"]["subject"] == "Payment reminder"


def test_send_email_demo_when_resend_unconfigured(db, monkeypatch):
    session, payment = db

    def fail_send(*args, **kwargs):
        raise AssertionError("Resend must not be called when unconfigured")

    monkeypatch.setattr(resend, "send_email", fail_send)
    settings = Settings(_env_file=None)

    result = agent_tools.send_email(
        session, settings, payment.id, CONVERSATION_ID, CUSTOMER_EMAIL, "Subject", "Body"
    )

    assert result == {"sent": True, "to": CUSTOMER_EMAIL, "demo": True}


def test_send_email_delivers_via_resend_when_configured(db, monkeypatch):
    session, payment = db
    calls = []

    def fake_send(settings, to, subject, body):
        calls.append({"to": to, "subject": subject, "body": body})
        return "msg_test_123"

    monkeypatch.setattr(resend, "send_email", fake_send)
    settings = Settings(_env_file=None, **RESEND_SETTINGS)

    result = agent_tools.send_email(
        session, settings, payment.id, CONVERSATION_ID, CUSTOMER_EMAIL.title(), "Payment reminder", "Body"
    )

    assert result == {"sent": True, "to": CUSTOMER_EMAIL, "email_id": "msg_test_123"}
    assert calls == [{"to": CUSTOMER_EMAIL, "subject": "Payment reminder", "body": "Body"}]


def test_send_email_maps_resend_failure_to_tool_error(db, monkeypatch):
    session, payment = db

    def failing_send(*args, **kwargs):
        raise ResendEmailError("Resend send request failed")

    monkeypatch.setattr(resend, "send_email", failing_send)
    settings = Settings(_env_file=None, **RESEND_SETTINGS)

    with pytest.raises(ToolError) as raised:
        agent_tools.send_email(
            session, settings, payment.id, CONVERSATION_ID, CUSTOMER_EMAIL, "Subject", "Body"
        )

    assert raised.value.code == "EMAIL_SEND_FAILED"
    assert raised.value.http_status == 502
