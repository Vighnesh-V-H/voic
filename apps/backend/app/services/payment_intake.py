"""Payment event intake: merchant resolution and payment correlation.

First slice of the intake deepening. The webhook route stays thin (verify,
delegate, acknowledge); everything the route needs to know about matching a
provider event to a Merchant-owned Payment lives behind this module's
interface:

- :func:`extract_provider_refs` pulls the Stripe-asserted references out of
  one event object, so callers never branch on Stripe shapes.
- :func:`correlate_payment` matches those references (plus Voic metadata
  inside an already-resolved merchant scope) to one Payment.
- :func:`resolve_connection` resolves the merchant's provider connection,
  keeping the signed-envelope primary path separate from the dev-only
  account-less fallback (:func:`resolve_connection_without_account`).

Enrichment, Payment status moves, and recovery fan-out follow as later
slices behind the same seam.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.payment import Payment
from app.models.provider_connection import ProviderConnection


@dataclass(frozen=True, slots=True)
class ProviderRefs:
    """Stripe-asserted references identifying which provider objects an event concerns.

    Unlike metadata strings, these are Stripe-asserted facts about the event,
    and each provider object belongs to exactly one connected account, so they
    are safe to correlate on with or without a merchant scope.
    """

    payment_id: str | None = None
    payment_link_id: str | None = None
    subscription_id: str | None = None
    invoice_id: str | None = None


def object_id(value: object) -> str | None:
    """Return a provider object ID from an expanded object or plain ID."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        candidate = value.get("id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def subscription_ref(event_object: Mapping[str, object]) -> str | None:
    """Extract a Stripe subscription ID from a Checkout Session or invoice object.

    Handles both the legacy top-level ``subscription`` field and the newer
    ``parent.subscription_details.subscription`` shape on invoices. Values may
    be plain IDs or expanded objects; anything else yields None.
    """
    candidate: object = event_object.get("subscription")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("id")
    if isinstance(candidate, str) and candidate:
        return candidate
    parent = event_object.get("parent")
    if isinstance(parent, Mapping):
        details = parent.get("subscription_details")
        if isinstance(details, Mapping):
            candidate = details.get("subscription")
            if isinstance(candidate, Mapping):
                candidate = candidate.get("id")
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def invoice_ref(event_object: Mapping[str, object]) -> str | None:
    """Extract a Stripe invoice ID from a Checkout Session or invoice-payment object.

    Values may be plain IDs or expanded objects; anything else yields None.
    """
    candidate: object = event_object.get("invoice")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("id")
    if isinstance(candidate, str) and candidate:
        return candidate
    return None


def extract_provider_refs(event_type: str, event_object: Mapping[str, object]) -> ProviderRefs:
    """Collect the Stripe-asserted references carried by one event object.

    Session, invoice, and invoice-payment IDs are not PaymentIntent IDs, so
    they never land on ``payment_id``; the nested payment intent inside
    ``invoice_payment`` events is captured so the matching
    ``payment_intent.*`` event correlates too.
    """
    payment_id = object_id(event_object.get("id"))
    related_payment_intent = object_id(event_object.get("payment_intent"))
    if event_type.startswith("invoice_payment."):
        payment = event_object.get("payment")
        related_payment_intent = (
            object_id(payment.get("payment_intent")) if isinstance(payment, Mapping) else None
        )
    if related_payment_intent is not None:
        payment_id = related_payment_intent
    elif event_type.startswith(("checkout.session.", "invoice.", "invoice_payment.")):
        payment_id = None
    payment_link_id = event_object.get("payment_link")
    return ProviderRefs(
        payment_id=payment_id if isinstance(payment_id, str) else None,
        payment_link_id=payment_link_id if isinstance(payment_link_id, str) else None,
        subscription_id=subscription_ref(event_object),
        invoice_id=invoice_ref(event_object),
    )


def _payment_by_ref(
    db: Session,
    field: object,
    value: str | None,
    *,
    merchant_id: str | None = None,
    connection: ProviderConnection | None = None,
) -> Payment | None:
    """Return the Payment carrying one provider reference, optionally merchant-scoped."""
    if value is None:
        return None
    statement = select(Payment).where(Payment.provider == "stripe", field == value)
    if merchant_id is not None and connection is not None:
        statement = statement.where(
            Payment.merchant_id == merchant_id,
            Payment.provider_connection_id == connection.id,
            Payment.provider_account_id == connection.provider_account_id,
        )
    return db.scalar(statement)


def correlate_payment(
    db: Session,
    refs: ProviderRefs,
    metadata: Mapping[str, object] | None = None,
    *,
    merchant_id: str | None = None,
    connection: ProviderConnection | None = None,
) -> Payment | None:
    """Locate the Voic payment an event concerns, or None if it matches none.

    Inside a resolved merchant scope, Voic metadata is consulted first, then
    the Stripe-asserted references in subscription, invoice, payment, and
    link order. Without a scope (account-less hint lookup), metadata is never
    consulted and the references are tried link-first; the hint only ever
    feeds merchant resolution, never payment selection.
    """
    scoped = merchant_id is not None and connection is not None
    if scoped:
        local_payment_id = metadata.get("voic_payment_id") if isinstance(metadata, Mapping) else None
        if isinstance(local_payment_id, str):
            payment = db.scalar(
                select(Payment).where(
                    Payment.id == local_payment_id,
                    Payment.merchant_id == merchant_id,
                    Payment.provider_connection_id == connection.id,
                    Payment.provider_account_id == connection.provider_account_id,
                )
            )
            if payment is not None:
                return payment
        for field, value in (
            (Payment.provider_subscription_id, refs.subscription_id),
            (Payment.provider_invoice_id, refs.invoice_id),
            (Payment.provider_payment_id, refs.payment_id),
        ):
            payment = _payment_by_ref(
                db, field, value, merchant_id=merchant_id, connection=connection
            )
            if payment is not None:
                return payment
        return _payment_by_ref(
            db,
            Payment.provider_payment_link_id,
            refs.payment_link_id,
            merchant_id=merchant_id,
            connection=connection,
        )
    for field, value in (
        (Payment.provider_payment_link_id, refs.payment_link_id),
        (Payment.provider_subscription_id, refs.subscription_id),
        (Payment.provider_invoice_id, refs.invoice_id),
        (Payment.provider_payment_id, refs.payment_id),
    ):
        payment = _payment_by_ref(db, field, value)
        if payment is not None:
            return payment
    return None


def resolve_connection_without_account(
    db: Session, settings: Settings, refs: ProviderRefs
) -> ProviderConnection | None:
    """Dev-only fallback adapter: resolve the merchant without a signed envelope.

    Production Connect delivery always carries the signed account envelope, so
    this path exists only for dashboard/CLI delivery without it (see
    ADR-0004). It never consults metadata: the merchant is resolved through
    Stripe-asserted provider references matched against stored Payments,
    explicit local configuration, or an unambiguous single connected account.
    """
    hint = correlate_payment(db, refs)
    if hint is not None:
        connection = db.scalar(
            select(ProviderConnection).where(
                ProviderConnection.id == hint.provider_connection_id,
                ProviderConnection.provider == "stripe",
            )
        )
        if connection is not None:
            return connection
    configured_account_id = (settings.stripe_webhook_account_id or "").strip()
    if configured_account_id:
        return db.scalar(
            select(ProviderConnection).where(
                ProviderConnection.provider == "stripe",
                ProviderConnection.provider_account_id == configured_account_id,
            )
        )
    # A single connected account is an unambiguous local-dev fallback.
    # Production Connect webhooks should always carry account/context.
    connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.provider == "stripe",
            ProviderConnection.status == "connected",
        )
    ).all()
    if len(connections) == 1:
        return connections[0]
    return None


def resolve_connection(
    db: Session, settings: Settings, account_id: str | None, refs: ProviderRefs
) -> ProviderConnection | None:
    """Resolve the merchant's provider connection for one webhook event.

    The signed connected-account envelope is the primary path whenever
    present; account-less events fall through to the dev-only fallback
    adapter. A None return means unroutable, and the caller decides between
    rejection (no envelope) and ignore (unknown or disconnected account).
    """
    if account_id is not None:
        return db.scalar(
            select(ProviderConnection).where(
                ProviderConnection.provider == "stripe",
                ProviderConnection.provider_account_id == account_id,
            )
        )
    return resolve_connection_without_account(db, settings, refs)
