# Voic Phase 1 Backend and Frontend Architecture

## 1. Objective

Voic is a SaaS application that connects a merchant's payment systems to a trusted foundation for future payment recovery. Phase 1 establishes the payment-provider foundation only:

```text
Merchant signs up
      |
      v
Merchant connects an existing Stripe account
      |
      v
Voic stores the provider connection
      |
      v
Voic reads Stripe products and prices
      |
      v
Voic creates Payments and Payment Links
      |
      v
Stripe sends Connect webhook events
      |
      v
Voic verifies, deduplicates, and persists payment events
      |
      v
Voic synchronizes its payment status
```

The complete Stripe integration contract is documented in `docs/stripe-connect.md`. That document is the source of truth for Stripe endpoint behavior. This architecture document defines the boundaries around it.

The voice agent, recovery rules, and production payments are later phases.

## 2. Technology

### Frontend

- Next.js
- TypeScript
- App Router
- Server and client components where appropriate

The frontend provides authentication, merchant onboarding, provider connection, catalog selection, payment and Payment Link actions, connection status, and recent payment-event visibility. It never receives platform secrets, OAuth credentials, webhook secrets, or raw webhook payloads.

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- Alembic

Provider-specific behavior stays behind a provider abstraction. API routes depend on the abstraction rather than the Stripe SDK directly.

## 3. Domain Model

```text
User
  |
  v
Merchant
  |
  v
ProviderConnection
  |
  +--> Stripe products and prices (owned by Stripe)
  +--> Payment
          |
          +--> Payment events
          +--> Payment Link (optional)
```

### User

A person who can sign in to Voic. In Phase 1, each user belongs to one merchant. Passwords are hashed when password authentication is used.

### Merchant

A business using Voic. A merchant owns its provider connections, payments, payment events, and future recovery activity. A merchant is not equivalent to a user or a Stripe account.

### Provider connection

An authorization relationship in which a merchant has granted Voic access to an external payment provider.

Minimum fields:

```text
id
merchant_id
provider
provider_account_id
mode
scope
status
created_at
updated_at
```

For Stripe, `provider_account_id` is the connected account ID returned as `stripe_user_id`. There is at most one active Stripe provider connection per merchant.

### Payment

A Voic-owned attempt to collect money for a merchant. It stores the Stripe PaymentIntent ID or Payment Link ID, the selected Stripe price ID, amount, currency, and current Voic payment status.

Payment statuses are:

```text
CREATED
PENDING
COMPLETED
FAILED
CANCELLED
```

### Payment event

A provider-originated record that tells Voic a payment-related event occurred. Events are immutable, retain the verified raw payload for restricted debugging, and have a uniqueness constraint on `(provider, provider_event_id)`.

## 4. Stripe Provider Connection

Voic uses Stripe Standard OAuth to connect an existing Stripe account.

```text
Authenticated merchant
      |
      v
Voic creates a cryptographically random state
      |
      v
Stripe authorization page
      |
      v
Voic validates state and authorization code
      |
      v
Voic stores stripe_user_id and connection metadata
```

The backend owns the OAuth flow. State is stored server-side, bound to the authenticated user and merchant, expires, and is single-use. A callback with a missing, expired, reused, or mismatched state is rejected before any token exchange.

Stripe's current API guidance recommends using the platform secret key with the connected account ID in the `Stripe-Account` header. Voic therefore stores the connected account ID, mode, granted scope, and connection status, but does not persist or return deprecated OAuth access or refresh tokens.

The platform secret key is server-only and must match the Stripe test mode used for the initial implementation. Reconnection to the same account updates the existing merchant/provider connection; reconnecting a different account replaces it and removes the previous account's Voic payments and payment events. Deauthorization or disconnect deletes the merchant's Voic-owned Stripe data (provider connections, payments, and payment events) while preserving the merchant and user records so the merchant stays signed in. Deletion is destructive: the frontend must obtain explicit merchant confirmation before calling disconnect, and the backend docstring records the same warning.

## 5. Stripe Catalog

Stripe is the catalog source of truth. Merchants create and manage products and prices in Stripe. Voic retrieves products and prices when needed, exposes a read-only selection view, and stores only the Stripe IDs required to associate a payment.

Voic does not create or duplicate Stripe products in Phase 1.

## 6. Payment and Payment Link Flow

All payment creation is scoped to the authenticated merchant's active provider connection. The backend validates that a requested Stripe price belongs to that connected account before creating a payment resource.

### PaymentIntent

`POST /api/v1/payments` creates a Stripe PaymentIntent for the selected one-time price and quantity. The PaymentIntent starts in a non-terminal Voic status and includes a non-sensitive Voic payment ID in Stripe metadata. The response may include Stripe's client secret for client-side confirmation; it must never include the platform secret or OAuth credentials.

### Payment Link

`POST /api/v1/payment-links` creates a Stripe-hosted Payment Link using an existing one-time Stripe price and quantity. The request includes the Voic payment ID in both Payment Link metadata and `payment_intent_data.metadata`, allowing the resulting PaymentIntent webhook to correlate the local payment after the merchant boundary is resolved from the signed event account. Voic stores and returns the hosted URL.

The frontend and any future voice agent consume the backend response. They never manufacture Stripe URLs.

## 7. Webhook Ingestion

Voic exposes:

```http
POST /api/v1/webhooks/stripe
```

This is a public endpoint protected by Stripe signature verification. It is configured once as a platform-level Connect webhook with `connect=true` and receives events for all connected accounts. The signing secret is deployment-managed through `STRIPE_CONNECT_WEBHOOK_SECRET`; it is not stored per merchant.

Processing order:

```text
Read raw request body
      |
      v
Read Stripe-Signature header
      |
      v
Verify signature with the Connect endpoint secret
      |
      v
Parse the event
      |
      v
Resolve event.account to exactly one ProviderConnection
      |
      v
Deduplicate provider_event_id
      |
      v
Persist PaymentEvent
      |
      v
Update the matching Payment when supported
      |
      v
Return 2xx quickly
```

Stripe's event `account` field (or the equivalent top-level `context` field in newer Stripe API versions) is the authoritative merchant boundary. Both are Stripe-signed envelope values. Customer email, phone, amount, description, frontend data, Stripe metadata, and any other untrusted values are never used to select a merchant; metadata (`voic_payment_id`) is only used to correlate a payment after the merchant boundary is resolved. An event with a missing account/context is rejected.

Phase 1 handles at least:

- `payment_intent.succeeded` -> `COMPLETED`
- `payment_intent.payment_failed` -> `FAILED`
- `account.application.deauthorized` -> delete the matching merchant's Voic-owned Stripe data (explicit delete-with-consent policy, see section 4)

Events may be duplicated or arrive out of order. Each event is persisted independently and no business logic assumes delivery order. Unknown connected accounts, invalid payloads, invalid signatures, and duplicate events have explicit outcomes and never cross merchant boundaries.

## 8. API Surface

Protected routes resolve every request as:

```text
authenticated user -> merchant -> merchant-owned resource
```

Stripe connection:

```http
GET /api/v1/stripe/connect
GET /api/v1/stripe/callback
DELETE /api/v1/stripe/connection
```

Catalog:

```http
GET /api/v1/stripe/products
GET /api/v1/stripe/products/{id}
```

Payments:

```http
POST /api/v1/payments
GET /api/v1/payments/{id}
```

Payment Links:

```http
POST /api/v1/payment-links
GET /api/v1/payment-links/{id}
```

Webhook:

```http
POST /api/v1/webhooks/stripe
```

Responses expose provider IDs, status, amount, currency, and hosted URLs where applicable. They never expose platform secrets, OAuth credentials, webhook secrets, or unrestricted raw webhook payloads.

## 9. Security and Tenant Isolation

Voic uses server-validated opaque HTTP-only sessions. The backend resolves the session to a user and merchant on every protected request. Browser code cannot read the session token.

Every merchant-owned query is scoped by the authenticated merchant. Merchant A cannot retrieve Merchant B's provider connections, payments, payment events, customer data, or raw webhook payloads.

Credentials and sensitive data follow these rules:

- Platform secret and webhook secret come from environment or secret management.
- Secrets are never committed, logged, or returned to the frontend.
- Raw webhook payloads are retained for restricted developer debugging only: stored server-side, never returned by merchant APIs, never logged, and never sent to the frontend. See ADR-0003 for the retention policy.
- Payment metadata contains only non-sensitive identifiers.
- Test mode uses synthetic data only.

## 10. Frontend

The minimal frontend includes:

- `/login`
- `/signup`
- `/dashboard`
- `/settings/integrations`

The integration view shows whether Stripe is connected, the connected account identifier in a safe display form, catalog products/prices, created payments and Payment Links, and recent normalized payment events. It does not display secrets or full raw payloads.

## 11. Testing

Automated tests exercise external behavior at the API boundary using a fake provider or mocked Stripe adapter. They cover:

- Signup, login, invalid credentials, and merchant resolution
- OAuth state generation, expiry, single-use validation, and callback handling
- Connected account storage without credential leakage
- Product and price retrieval scoped to the connected account
- PaymentIntent and Payment Link creation from existing prices
- Metadata-based payment correlation
- Valid and invalid raw-body webhook signatures
- Malformed payloads, missing account/context, and unknown connected accounts
- Duplicate event idempotency and out-of-order event persistence
- Success and failure payment-status synchronization
- Deauthorization and disconnect deletion of Voic-owned Stripe data with explicit merchant confirmation
- Metadata can never select a merchant (correlation only after the signed account boundary is resolved)
- Cross-merchant access rejection

Manual acceptance runs entirely in Stripe Test Mode. The Stripe CLI or another temporary public HTTPS endpoint may forward Connect events to local development. No production credentials or real payments are required.

## 12. Out of Scope

Phase 1 does not include:

- Product creation from Voic
- Subscriptions, recurring prices, refunds, disputes, payouts, or chargebacks
- Production credentials or live payments
- Voice agents, telephony, STT, TTS, LLMs, or LangGraph
- RecoveryCase, eligibility, calling, email delivery, or recovery attribution
- Analytics beyond basic integration health and recent payment events

## 13. Definition of Done

Phase 1 is complete when:

- The Next.js frontend, FastAPI backend, PostgreSQL database, and migrations run.
- A user and merchant can sign up and authenticate.
- An existing Stripe Test Mode account can connect through Standard OAuth with CSRF-protected state.
- The connected Stripe account ID and connection metadata are stored without exposing credentials.
- Products and prices can be retrieved from the connected account.
- A PaymentIntent and a Payment Link can be created from an existing one-time price.
- The centralized Connect webhook verifies the raw request body.
- The event's connected account maps to exactly one merchant.
- Duplicate events are idempotent and raw verified payloads are retained per the restricted-debugging policy (ADR-0003).
- `payment_intent.succeeded` and `payment_intent.payment_failed` synchronize Payment status.
- Merchant isolation is covered by automated tests.
- A Stripe Test Mode payment failure can be forwarded to Voic and inspected in the database or dashboard.

Once these criteria pass, stop Phase 1. The backend remains the source of truth for future recovery work.
