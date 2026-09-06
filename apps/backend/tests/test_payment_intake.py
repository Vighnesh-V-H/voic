"""Tests at the Payment event intake module's interface.

These pin correlation and merchant-resolution behaviour through
``app.services.payment_intake`` directly. The HTTP-level routing matrix in
``test_stripe.py`` and the trigger tests in ``test_call_trigger.py`` cover
the route around it and stay unchanged.
"""

import pytest

from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.provider_connection import ProviderConnection
from app.services.payment_intake import (
    ProviderRefs,
    correlate_payment,
    extract_provider_refs,
    resolve_connection,
)


@pytest.fixture()
def db(client):
    override = app.dependency_overrides[get_db]
    session_generator = override()
    session = next(session_generator)
    yield session
    session_generator.close()


def make_merchant(db, name="Acme"):
    merchant = Merchant(name=name)
    db.add(merchant)
    db.flush()
    return merchant


def make_connection(db, merchant_id, account_id="acct_test_123", status="connected"):
    connection = ProviderConnection(
        merchant_id=merchant_id,
        provider="stripe",
        provider_account_id=account_id,
        mode="test",
        scope="read_write",
        status=status,
    )
    db.add(connection)
    db.flush()
    return connection


def make_payment(db, merchant_id, connection, **refs):
    payment = Payment(
        merchant_id=merchant_id,
        provider_connection_id=connection.id,
        provider="stripe",
        provider_account_id=connection.provider_account_id,
        provider_price_id="price_123",
        amount=2500,
        currency="usd",
        status="CREATED",
        **refs,
    )
    db.add(payment)
    db.flush()
    return payment


def test_extract_refs_payment_intent():
    refs = extract_provider_refs("payment_intent.payment_failed", {"id": "pi_123"})

    assert refs == ProviderRefs(payment_id="pi_123")


def test_extract_refs_checkout_session_never_uses_session_id():
    refs = extract_provider_refs(
        "checkout.session.completed",
        {
            "id": "cs_123",
            "payment_intent": "pi_456",
            "subscription": "sub_789",
            "invoice": "in_012",
            "payment_link": "plink_345",
        },
    )

    # Only real PaymentIntent IDs ride on payment_id; session IDs must not
    # pollute the column or later PI events won't correlate.
    assert refs == ProviderRefs(
        payment_id="pi_456",
        payment_link_id="plink_345",
        subscription_id="sub_789",
        invoice_id="in_012",
    )


def test_extract_refs_invoice_payment_captures_nested_intent():
    refs = extract_provider_refs(
        "invoice_payment.paid",
        {"id": "invpay_123", "payment": {"payment_intent": "pi_999"}},
    )

    assert refs.payment_id == "pi_999"


def test_correlate_scoped_metadata_first(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)
    by_metadata = make_payment(db, merchant.id, connection)
    make_payment(db, merchant.id, connection, provider_payment_id="pi_shared")

    found = correlate_payment(
        db,
        ProviderRefs(payment_id="pi_shared"),
        {"voic_payment_id": by_metadata.id},
        merchant_id=merchant.id,
        connection=connection,
    )

    assert found is not None and found.id == by_metadata.id


def test_correlate_scoped_subscription_without_metadata(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)
    payment = make_payment(db, merchant.id, connection, provider_subscription_id="sub_1")

    found = correlate_payment(
        db,
        ProviderRefs(subscription_id="sub_1"),
        {},
        merchant_id=merchant.id,
        connection=connection,
    )

    assert found is not None and found.id == payment.id


def test_correlate_scoped_never_crosses_merchant(db):
    merchant_a = make_merchant(db, "A")
    merchant_b = make_merchant(db, "B")
    connection_a = make_connection(db, merchant_a.id, account_id="acct_a")
    connection_b = make_connection(db, merchant_b.id, account_id="acct_b")
    other = make_payment(db, merchant_b.id, connection_b)
    make_payment(
        db, merchant_b.id, connection_b, provider_payment_id="pi_other_merchant"
    )

    assert (
        correlate_payment(
            db,
            ProviderRefs(payment_id="pi_other_merchant"),
            {"voic_payment_id": other.id},
            merchant_id=merchant_a.id,
            connection=connection_a,
        )
        is None
    )


def test_correlate_unscoped_ignores_metadata(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)
    by_metadata = make_payment(db, merchant.id, connection)
    by_link = make_payment(db, merchant.id, connection, provider_payment_link_id="plink_1")

    found = correlate_payment(
        db,
        ProviderRefs(payment_link_id="plink_1"),
        {"voic_payment_id": by_metadata.id},
    )

    assert found is not None and found.id == by_link.id


def test_correlate_returns_none_when_no_match(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)
    make_payment(db, merchant.id, connection, provider_payment_id="pi_something_else")

    assert (
        correlate_payment(
            db,
            ProviderRefs(payment_id="pi_unknown"),
            {},
            merchant_id=merchant.id,
            connection=connection,
        )
        is None
    )


def test_resolve_connection_signed_envelope(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)

    found = resolve_connection(db, Settings(), "acct_test_123", ProviderRefs())

    assert found is not None and found.id == connection.id


def test_resolve_connection_signed_envelope_unknown_account(db):
    make_merchant(db)

    assert resolve_connection(db, Settings(), "acct_unknown", ProviderRefs()) is None


def test_resolve_connection_fallback_via_hint(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)
    make_payment(db, merchant.id, connection, provider_payment_id="pi_hint")

    found = resolve_connection(db, Settings(), None, ProviderRefs(payment_id="pi_hint"))

    assert found is not None and found.id == connection.id


def test_resolve_connection_fallback_single_connection(db):
    merchant = make_merchant(db)
    connection = make_connection(db, merchant.id)

    found = resolve_connection(db, Settings(), None, ProviderRefs())

    assert found is not None and found.id == connection.id


def test_resolve_connection_fallback_ambiguous_returns_none(db):
    merchant = make_merchant(db)
    make_connection(db, merchant.id, account_id="acct_one")
    make_connection(db, merchant.id, account_id="acct_two")

    assert resolve_connection(db, Settings(), None, ProviderRefs()) is None


def test_resolve_connection_fallback_configured_account(db):
    merchant = make_merchant(db)
    make_connection(db, merchant.id, account_id="acct_other")
    configured = make_connection(db, merchant.id, account_id="acct_configured")
    settings = Settings(stripe_webhook_account_id="acct_configured")

    found = resolve_connection(db, settings, None, ProviderRefs())

    assert found is not None and found.id == configured.id
