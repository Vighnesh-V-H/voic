# 04: Replace Razorpay Phase 1 integration with Stripe Connect payments

> Synced from https://github.com/Vighnesh-V-H/voic/issues/4
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-03T12:53:45Z | Updated: 2026-09-03T12:53:45Z
> Sub-issues: #5, #6, #7, #8, #9 (0/5 completed)

**Parent:** Epic — supersedes provider scope of #3 (does not modify or close #3).

**What to build:** Replace the Razorpay-oriented Phase 1 integration with a Stripe Connect integration in Stripe Test Mode. A merchant can connect an existing Stripe account through Standard OAuth, view Stripe-owned products and prices, create PaymentIntents and Stripe-hosted Payment Links from existing one-time prices, and receive verified Connect webhook events that persist PaymentEvents and synchronize VOIC-owned Payment status.

**Status:** ready-for-agent

## Problem Statement

Voic currently has only authentication and merchant foundations. The architecture still describes a Razorpay integration, while the product requirement is to connect merchants' existing Stripe accounts and own a trustworthy payment state through Stripe Connect.

This issue supersedes the provider scope described by #3. It does not modify or close that issue.

## Solution

Replace the Razorpay-oriented Phase 1 integration with a Stripe Connect integration in Stripe Test Mode. A merchant can connect an existing Stripe account through Standard OAuth, view Stripe-owned products and prices, create PaymentIntents and Stripe-hosted Payment Links from existing one-time prices, and receive verified Connect webhook events that persist PaymentEvents and synchronize VOIC-owned Payment status.

Stripe remains the product catalog source of truth. VOIC uses the platform secret key with the connected account ID in the `Stripe-Account` header and does not persist deprecated OAuth access or refresh tokens.

## User Stories

1. As a merchant, I want to connect my existing Stripe account to Voic, so that Voic can act on behalf of that account.
2. As a merchant, I want OAuth state protection, so that a forged callback cannot connect another account to my merchant.
3. As a merchant, I want to see my Stripe products and prices in Voic, so that I can select what to charge without duplicating my catalog.
4. As a merchant, I want to create a PaymentIntent from an existing one-time price, so that my customers can complete payment through Stripe.
5. As a merchant, I want to create a Stripe-hosted Payment Link, so that I can share a legitimate checkout URL.
6. As a merchant, I want payment success and failure reflected in Voic, so that Voic owns a reliable payment status.
7. As a developer, I want verified and idempotent Connect webhooks, so that duplicate or forged events cannot corrupt payment state.
8. As a merchant, I want my data isolated from other merchants, so that provider connections, payments, and payment events remain private.
9. As a developer, I want a Test Mode acceptance path, so that the complete integration can be validated without live credentials or real payments.

## Implementation Decisions

- Stripe Standard OAuth is used for existing Stripe accounts.
- OAuth state is random, server-stored, bound to the authenticated user and merchant, expiring, and single-use.
- The provider abstraction is the seam between API/services and Stripe SDK details.
- API tests use a fake provider with real database persistence; the Stripe adapter is tested with mocked SDK responses.
- ProviderConnection stores the merchant, provider, connected Stripe account ID, mode, scope, status, and timestamps.
- The platform secret key and connected account ID authenticate server-side Stripe API calls. OAuth access and refresh tokens are not persisted or returned.
- Stripe products and prices are read-only in Voic. Product creation remains in Stripe.
- Payments use existing one-time Stripe prices and quantity; arbitrary client-supplied amounts are not accepted.
- PaymentIntent and Payment Link creation creates a Voic-owned Payment and writes a non-sensitive Voic payment ID into Stripe metadata.
- Payment Links also put the internal ID in `payment_intent_data.metadata` so generated PaymentIntent events correlate deterministically.
- A single platform-level Connect webhook receives events for connected accounts using `STRIPE_CONNECT_WEBHOOK_SECRET`.
- The webhook verifies the raw request body with `Stripe-Signature` before parsing JSON.
- The event top-level `account` identifies the connected account and is the merchant boundary.
- PaymentEvent uniqueness is enforced by `(provider, provider_event_id)`.
- `payment_intent.succeeded` maps to `COMPLETED`; `payment_intent.payment_failed` maps to `FAILED`.
- Disconnect and deauthorization preserve historical payments and payment events.
- The existing server-validated HTTP-only session ADR and merchant-level authorization remain in force.

## Testing Decisions

Tests cover OAuth state validation, connection storage and credential non-disclosure, catalog scoping, PaymentIntent and Payment Link creation, metadata correlation, raw-body signature verification, malformed payloads, unknown accounts, duplicates, out-of-order events, status synchronization, disconnect behavior, and cross-merchant isolation. Existing authentication tests remain green.

Manual acceptance uses Stripe Test Mode and Stripe CLI or another temporary public HTTPS forwarding endpoint.

## Out of Scope

- Razorpay implementation or migration of historical Razorpay data
- Creating products from Voic
- Subscriptions, recurring prices, refunds, disputes, payouts, chargebacks, and production payments
- Voice, telephony, AI, recovery cases, eligibility, email, and recovery attribution
- Full analytics beyond basic connection health and recent payment events

## Further Notes

The architecture and domain glossary have been updated to use Stripe terminology. Current Stripe documentation was checked for Standard OAuth, platform Connect webhooks, raw-body signatures, connected-account identity, PaymentIntent metadata, and Payment Link metadata propagation.
