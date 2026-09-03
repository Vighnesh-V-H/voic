# 08: Verify Stripe Connect webhooks and synchronize payment status

> Synced from https://github.com/Vighnesh-V-H/voic/issues/8
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-03T12:54:24Z | Updated: 2026-09-03T12:54:24Z
> Parent: #4 | Blocked by: #7

**What to build:** Voic receives Stripe Connect events through one platform webhook, verifies them against the raw body, maps the connected account to exactly one merchant, persists each event idempotently, and synchronizes the matching Payment status.

**Blocked by:** #7

**Status:** ready-for-agent

- [ ] A public Stripe webhook endpoint accepts Connect events for connected accounts.
- [ ] The handler reads the raw request body and verifies the `Stripe-Signature` header before parsing JSON.
- [ ] Invalid signatures and malformed payloads are rejected without persistence.
- [ ] The event's top-level connected account ID resolves to exactly one active or known merchant provider connection.
- [ ] Unknown connected accounts cannot create merchant-owned records and receive an explicit error outcome.
- [ ] PaymentEvents retain provider, provider event ID, event type, provider payment ID, normalized safe fields, raw payload, occurrence time, and processing time.
- [ ] Duplicate provider events are ignored safely through a database uniqueness constraint and do not mutate payment state twice.
- [ ] `payment_intent.succeeded` synchronizes the correlated Payment to `COMPLETED`.
- [ ] `payment_intent.payment_failed` synchronizes the correlated Payment to `FAILED`.
- [ ] Payment Link-generated PaymentIntents correlate through the Voic metadata identifier.
- [ ] Events are persisted independently without assuming delivery order.
- [ ] `account.application.deauthorized` marks the provider connection disconnected while preserving historical data.
- [ ] The handler returns quickly after persistence and does not perform expensive downstream work.
- [ ] Automated tests cover valid and invalid signatures, raw-body handling, malformed events, unknown accounts, duplicates, out-of-order delivery, status synchronization, and tenant boundaries.

## Full body

## Parent

Part of #4.

## What to build

Voic receives Stripe Connect events through one platform webhook, verifies them against the raw body, maps the connected account to exactly one merchant, persists each event idempotently, and synchronizes the matching Payment status.

## Acceptance criteria

- [ ] A public Stripe webhook endpoint accepts Connect events for connected accounts.
- [ ] The handler reads the raw request body and verifies the `Stripe-Signature` header before parsing JSON.
- [ ] Invalid signatures and malformed payloads are rejected without persistence.
- [ ] The event's top-level connected account ID resolves to exactly one active or known merchant provider connection.
- [ ] Unknown connected accounts cannot create merchant-owned records and receive an explicit error outcome.
- [ ] PaymentEvents retain provider, provider event ID, event type, provider payment ID, normalized safe fields, raw payload, occurrence time, and processing time.
- [ ] Duplicate provider events are ignored safely through a database uniqueness constraint and do not mutate payment state twice.
- [ ] `payment_intent.succeeded` synchronizes the correlated Payment to `COMPLETED`.
- [ ] `payment_intent.payment_failed` synchronizes the correlated Payment to `FAILED`.
- [ ] Payment Link-generated PaymentIntents correlate through the Voic metadata identifier.
- [ ] Events are persisted independently without assuming delivery order.
- [ ] `account.application.deauthorized` marks the provider connection disconnected while preserving historical data.
- [ ] The handler returns quickly after persistence and does not perform expensive downstream work.
- [ ] Automated tests cover valid and invalid signatures, raw-body handling, malformed events, unknown accounts, duplicates, out-of-order delivery, status synchronization, and tenant boundaries.

## Blocked by

- #7
