import json
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from app.core.config import Settings, get_settings
from app.main import app
from app.models.call_attempt import CallAttempt
from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.provider_connection import ProviderConnection
from app.services.calls import vobiz
from app.services.calls.vobiz import callback_signature, place_call, recovery_answer_url
from tests.test_call_trigger import VOBIZ_SETTINGS, db_session, fake_provider
from tests.test_stripe import connected_payment


class FakeVobizResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"request_uuid":"call_test_123"}'


def test_place_call_uses_per_payment_answer_url(monkeypatch):
    settings = Settings(
        **{**VOBIZ_SETTINGS, "vobiz_answer_url": "https://legacy.example/static-answer"},
    )
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        assert timeout == 10
        return FakeVobizResponse()

    monkeypatch.setattr(vobiz.urllib.request, "urlopen", fake_urlopen)

    assert (
        place_call(
            settings,
            to="+919876543210",
            payment_id="payment/&-1",
            attempt_id="attempt-1",
        )
        == "call_test_123"
    )

    body = json.loads(requests[0].data)
    answer = urlparse(body["answer_url"])
    assert answer.path == "/api/v1/voice/answer"
    assert parse_qs(answer.query) == {
        "payment_id": ["payment/&-1"],
        "attempt_id": ["attempt-1"],
        "signature": [
            callback_signature(
                VOBIZ_SETTINGS["voice_callback_token"], "payment/&-1", "attempt-1"
            )
        ],
    }
    assert "legacy.example" not in body["answer_url"]


def test_recovery_answer_url_strips_base_trailing_slash():
    settings = Settings(
        **{**VOBIZ_SETTINGS, "vobiz_public_base_url": "https://voic.example.com/"}
    )

    assert recovery_answer_url(settings, "payment-1", "attempt-1") == (
        "https://voic.example.com/api/v1/voice/answer?payment_id=payment-1&attempt_id=attempt-1&signature="
        f"{callback_signature('token_test_123', 'payment-1', 'attempt-1')}"
    )


def test_answer_returns_valid_recovery_xml_for_failed_payment(client, fake_provider, db_session):
    payment_id = connected_payment(client, fake_provider)
    payment = db_session.get(Payment, payment_id)
    payment.status = "FAILED"
    attempt = CallAttempt(
        merchant_id=payment.merchant_id,
        payment_id=payment.id,
        provider="vobiz",
        status="PLACED",
    )
    db_session.add(attempt)
    db_session.commit()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, **{**VOBIZ_SETTINGS, "vobiz_public_base_url": "", "voice_ws_base_url": ""}
    )

    try:
        response = client.post(recovery_answer_url(Settings(_env_file=None, **VOBIZ_SETTINGS), payment_id, attempt.id))
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    document = ElementTree.fromstring(response.content)
    assert document.tag == "Response"
    assert document.findtext("Speak") == (
        "This is a reminder that your recent payment could not be completed. "
        "Please contact the merchant to complete your payment. Goodbye."
    )
    assert document.find("Hangup") is not None


def test_answer_returns_safe_xml_for_unknown_or_completed_payment(client, fake_provider, db_session):
    payment_id = connected_payment(client, fake_provider)
    payment = db_session.get(Payment, payment_id)
    attempt = CallAttempt(
        merchant_id=payment.merchant_id,
        payment_id=payment.id,
        provider="vobiz",
        status="PLACED",
    )
    db_session.add(attempt)
    db_session.commit()
    settings = Settings(_env_file=None, **VOBIZ_SETTINGS)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **VOBIZ_SETTINGS)

    try:
        unknown = client.post(recovery_answer_url(settings, "missing-payment", "attempt-1"))
        completed = client.post(recovery_answer_url(settings, payment_id, attempt.id))
    finally:
        app.dependency_overrides.pop(get_settings, None)

    for response in (unknown, completed):
        assert response.status_code == 200
        document = ElementTree.fromstring(response.content)
        message = document.findtext("Speak")
        assert message is not None
        assert "could not verify this payment reminder" in message
        assert "missing-payment" not in response.text
        assert "token_test_123" not in response.text


def test_answer_does_not_cross_merchant_call_attempts(client, fake_provider, db_session):
    payment_id = connected_payment(client, fake_provider)
    payment = db_session.get(Payment, payment_id)
    payment.status = "FAILED"
    other_merchant = Merchant(name="Other Merchant")
    other_connection = ProviderConnection(
        merchant=other_merchant,
        provider="stripe",
        provider_account_id="acct_other",
        mode="test",
        scope="read_write",
        status="connected",
    )
    other_payment = Payment(
        merchant=other_merchant,
        provider_connection=other_connection,
        provider="stripe",
        provider_account_id="acct_other",
        provider_price_id="price_other",
        amount=1000,
        currency="usd",
        status="FAILED",
    )
    other_attempt = CallAttempt(
        merchant=other_merchant,
        payment=other_payment,
        provider="vobiz",
        status="PLACED",
    )
    db_session.add_all([other_merchant, other_connection, other_payment, other_attempt])
    db_session.commit()
    settings = Settings(_env_file=None, **VOBIZ_SETTINGS)
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = client.post(recovery_answer_url(settings, payment_id, other_attempt.id))
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert "could not verify this payment reminder" in response.text


def test_answer_rejects_missing_or_wrong_callback_signature(client):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **VOBIZ_SETTINGS)
    try:
        missing = client.post("/api/v1/voice/answer?payment_id=payment-1")
        wrong = client.post(
            "/api/v1/voice/answer?payment_id=payment-1&attempt_id=attempt-1&signature=wrong"
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert missing.status_code == 403
    assert missing.json() == {"detail": "VOICE_CALLBACK_UNAUTHORIZED"}
    assert wrong.status_code == 403
    assert wrong.json() == {"detail": "VOICE_CALLBACK_UNAUTHORIZED"}
