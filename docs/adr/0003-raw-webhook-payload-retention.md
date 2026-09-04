# ADR-0003: Raw Webhook Payload Retention

## Status

Accepted

## Context

Voic persists each verified Stripe webhook event as an immutable `PaymentEvent` with a uniqueness constraint on `(provider, provider_event_id)`. Debugging signature, correlation, and status-sync issues requires the exact bytes Stripe sent, so the verified raw payload is stored alongside the normalized fields. Raw payloads can contain customer data from the connected Stripe account, so their handling must be explicit.

## Decision

Raw verified webhook payloads are retained under a restricted-debugging policy:

- Stored server-side in the `payment_events.raw_payload` column for every persisted event.
- Never returned by merchant APIs (`PaymentEventResponse` exposes only normalized fields; `tests/test_stripe.py` asserts `raw_payload` is absent).
- Never logged and never sent to the frontend.
- Readable only through direct database access by an operator, and always scoped by `merchant_id` like any other merchant-owned record.
- No field-level encryption at rest in Phase 1; protection relies on database access control and the exclusions above.

## Consequences

- Operators can replay or inspect the exact Stripe bytes when webhook handling misbehaves.
- Any future merchant-facing event-detail view must keep excluding the raw payload unless this ADR is revised.
- If compliance or customer-data requirements tighten, the next step is field-level encryption or scheduled redaction of `raw_payload`, not silent exposure.

## Alternatives considered

- Not storing raw payloads was rejected because normalized fields alone are insufficient to diagnose signature, versioning, and correlation failures.
- Returning raw payloads through the merchant API was rejected because raw payloads are provider-originated data, not normal merchant API data, and cross-merchant leakage must stay impossible by construction.
