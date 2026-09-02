# Voic — Phase 1 Backend & Frontend Implementation Specification

## 1. Project Overview

Build **Voic**, a SaaS application that will eventually use a Hinglish voice agent to recover failed customer payments for merchants.

The eventual product flow is:

```text
Customer attempts payment
        ↓
Payment fails
        ↓
Voic receives payment failure
        ↓
Voic determines whether the failure is eligible for recovery
        ↓
Voic calls the customer using a voice agent
        ↓
Agent understands what went wrong
        ↓
If customer agrees, Voic sends a payment/checkout link
        ↓
Customer completes payment
        ↓
Voic detects successful payment
        ↓
Voic attributes the payment to the recovery attempt
        ↓
Merchant sees recovered money in dashboard
```

However, **this specification covers only Phase 1**.

### Phase 1 objective

Prove that the fundamental payment-provider integration works:

```text
Merchant signs up
      ↓
Merchant connects Razorpay through OAuth
      ↓
Voic securely stores the connection
      ↓
Voic receives Razorpay webhook events
      ↓
Voic verifies the webhook
      ↓
Voic identifies the correct merchant
      ↓
Voic persists the payment event
      ↓
Developer can inspect the event in the backend/database
```

We are intentionally **not building the voice agent yet**.

Do not introduce ElevenLabs, Vobiz, LangGraph, telephony providers, email delivery, or AI orchestration in this phase.

---

# 2. Technology Stack

## Frontend

Use:

* Next.js
* TypeScript
* App Router
* Server/client components where appropriate
* Standard modern React patterns

The frontend is responsible for:

* Authentication UI
* Merchant onboarding UI
* Payment-provider connection UI
* OAuth initiation
* OAuth success/failure states
* Basic connection status
* Basic developer/debug visibility if useful

Do not put payment-provider secrets or OAuth client secrets in the browser.

---

## Backend

Use:

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* PostgreSQL
* Alembic for migrations

Recommended project structure:

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── merchants.py
│   │   ├── integrations.py
│   │   └── webhooks.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── merchant.py
│   │   ├── provider_connection.py
│   │   └── payment_event.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── merchant.py
│   │   ├── integration.py
│   │   └── webhook.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── merchant_service.py
│   │   └── providers/
│   │       ├── base.py
│   │       └── razorpay.py
│   │
│   └── workers/
│       └── ...
│
├── migrations/
├── tests/
├── pyproject.toml
└── .env.example
```

The exact structure can change if there is a better clean architecture, but provider-specific logic must not leak throughout the application.

---

# 3. Important Architectural Principle

Voic must own its own internal state.

The payment provider is an external system.

Do not make the frontend or future voice agent directly responsible for interpreting the provider's state.

The desired architecture is:

```text
                External Systems
                     │
                     ▼
             Payment Provider
                     │
              OAuth / Webhooks
                     │
                     ▼
              Voic Backend
                     │
          ┌──────────┴──────────┐
          │                     │
      PostgreSQL            Services
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
                  Voic
```

The future voice agent will consume Voic-owned context rather than querying Razorpay directly.

---

# 4. Core Domain Model

The minimum domain model for Phase 1 is:

```text
User
  │
  ▼
Merchant
  │
  ▼
ProviderConnection
  │
  ▼
PaymentEvent
```

## User

Represents a person who can log into Voic.

Minimum fields:

```text
id
email
password_hash OR external-auth identifier
created_at
updated_at
```

Do not store plaintext passwords.

---

# 5. Merchant

A merchant is the business using Voic.

Minimum fields:

```text
id
name
created_at
updated_at
```

A user should be associated with a merchant.

For Phase 1, it is acceptable to support:

```text
one user → one merchant
```

But design the database so that this can later become:

```text
merchant
   ├── users
   ├── provider connections
   ├── recovery cases
   └── settings
```

Do not make the merchant equivalent to the user.

---

# 6. ProviderConnection

This is one of the most important objects in the system.

It represents:

> "Merchant X has authorized Voic to access Provider Y."

Example:

```text
ProviderConnection
------------------
id
merchant_id
provider
provider_account_id
access_token_encrypted
refresh_token_encrypted
access_token_expires_at
scopes
status
created_at
updated_at
```

For Razorpay:

```text
provider = "razorpay"
provider_account_id = razorpay_account_id
```

Razorpay's OAuth flow returns a `razorpay_account_id`, which identifies the sub-merchant account that granted authorization.

---

# 7. Token Security

OAuth credentials are sensitive secrets.

Never:

* expose access tokens to Next.js client code
* return tokens from API responses
* put tokens in browser localStorage
* log tokens
* log authorization codes
* commit tokens to Git
* store plaintext tokens if secure encryption-at-rest is available

At minimum:

```text
Database
    ↓
Encrypted token storage
```

Use application-level encryption for:

```text
access_token
refresh_token
```

The encryption key must come from an environment/secret-management system and must not be stored in PostgreSQL.

For local development, environment variables are acceptable.

Example:

```env
DATABASE_URL=...
JWT_SECRET=...
RAZORPAY_CLIENT_ID=...
RAZORPAY_CLIENT_SECRET=...
TOKEN_ENCRYPTION_KEY=...
```

Never commit `.env`.

Provide:

```text
.env.example
```

containing variable names only.

---

# 8. Razorpay OAuth

Razorpay OAuth must be implemented on the backend.

Razorpay's current partner OAuth documentation describes an authorization-code flow:

```text
Voic
  ↓
Razorpay authorization page
  ↓
Merchant authorizes Voic
  ↓
Razorpay redirects to Voic callback
  ↓
Voic receives authorization code
  ↓
Voic exchanges code server-side
  ↓
access_token
refresh_token
razorpay_account_id
  ↓
store securely
```

Razorpay requires technology partners to register an application and use OAuth for accessing sub-merchant resources.

---

# 9. OAuth State / CSRF Protection

The OAuth flow MUST use a cryptographically random `state`.

When the merchant clicks:

```text
Connect Razorpay
```

the backend must:

1. Generate a random state.
2. Associate it with the currently authenticated merchant/user.
3. Store it server-side.
4. Redirect the user to Razorpay.
5. Receive the callback.
6. Validate the returned state.
7. Reject the callback if the state does not match.
8. Only then exchange the authorization code.

Razorpay explicitly documents the `state` mechanism for CSRF protection.

Do not trust the OAuth callback simply because it contains a valid-looking `code`.

---

# 10. OAuth API Design

Create an endpoint similar to:

```http
GET /api/integrations/razorpay/connect
```

Purpose:

Return or perform the redirect to Razorpay authorization.

Then:

```http
GET /api/integrations/razorpay/callback
```

Purpose:

Handle the OAuth callback.

After successful OAuth:

```text
authorization code
        ↓
backend token exchange
        ↓
encrypted token storage
        ↓
ProviderConnection
```

The frontend should ultimately see something like:

```json
{
  "provider": "razorpay",
  "connected": true
}
```

Never:

```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

---

# 11. OAuth Scopes

For Phase 1, request only the scopes genuinely required for the integration.

Razorpay documents `read_only` and `read_write` scopes, with read/write allowing creation and modification of resources.

Do not request broad write permissions simply because they may be useful later.

Initially, the goal is:

```text
read payment information
receive payment events
identify the merchant account
```

If a later phase needs write permissions—for example creating payment links—add that requirement explicitly.

---

# 12. Refresh Token Handling

The backend must treat access tokens as expiring credentials.

Razorpay currently documents access tokens as expiring after 90 days and provides a refresh-token flow that returns a new access token and refresh token. The old refresh token becomes invalid when the new pair is issued.

Implement a provider service abstraction:

```python
class PaymentProvider:
    async def get_valid_access_token(
        self,
        connection: ProviderConnection
    ) -> str:
        ...
```

The service should:

1. Check whether the access token is still valid.
2. Return it if valid.
3. Refresh if required.
4. Persist the new access token.
5. Persist the new refresh token.
6. Update expiry.
7. Return the new access token.

Do not implement token refresh logic directly inside random API routes.

---

# 13. Provider Abstraction

Even though Phase 1 initially targets Razorpay, the architecture should support multiple providers.

Create an interface:

```python
class PaymentProvider(ABC):

    async def exchange_oauth_code(...):
        ...

    async def refresh_access_token(...):
        ...

    async def get_account(...):
        ...

    async def create_webhook(...):
        ...

    async def normalize_webhook(...):
        ...
```

Then:

```text
PaymentProvider
      │
      ├── RazorpayProvider
      │
      └── PolarProvider (future)
```

Do not build Polar yet.

But do not hard-code the entire backend around Razorpay either.

---

# 14. Webhook Architecture

The second major Phase 1 feature is webhook ingestion.

The basic flow:

```text
Razorpay
   │
   │ HTTP POST
   ▼
Voic webhook endpoint
   │
   ├── verify signature
   ├── identify event
   ├── identify merchant
   ├── deduplicate
   └── persist event
```

Razorpay sends webhook events asynchronously to the configured URL. Their documentation specifically recommends webhooks for automation and notes that webhook events can be duplicated or arrive out of order.

---

# 15. Webhook Endpoint

Create:

```http
POST /api/webhooks/razorpay
```

This endpoint is public because Razorpay must be able to reach it.

However, it must not be unauthenticated in the security sense.

The request must be verified using the Razorpay webhook signature.

Razorpay signs webhook payloads using HMAC-SHA256 and sends the signature in:

```text
X-Razorpay-Signature
```

The signature must be calculated against the **raw request body**. Do not parse and then reserialize the JSON before signature verification.

---

# 16. Webhook Verification

Correct sequence:

```text
HTTP request
     ↓
Read raw request body
     ↓
Read X-Razorpay-Signature
     ↓
Determine appropriate webhook secret
     ↓
HMAC-SHA256(raw_body, webhook_secret)
     ↓
Compare securely
     ↓
Only then parse JSON
```

Never:

```text
parse JSON
   ↓
serialize JSON
   ↓
verify signature
```

Razorpay explicitly warns against parsing/casting the body before validation.

---

# 17. Webhook Secrets

Each provider connection/webhook configuration may require a secret.

Do not use:

```text
RAZORPAY_CLIENT_SECRET
```

as the webhook secret.

They are different credentials.

Store webhook secrets securely/encrypted.

Example:

```text
ProviderConnection
        │
        └── webhook_secret_encrypted
```

If the architecture later supports multiple webhook endpoints per merchant, introduce a separate `WebhookEndpoint` model.

For Phase 1, keep the model simple unless the provider requires otherwise.

---

# 18. Merchant Identification

This is a critical invariant.

Every payment event received by Voic must be mapped to exactly one merchant.

Conceptually:

```text
Razorpay event
      ↓
Razorpay account identity
      ↓
ProviderConnection
      ↓
merchant_id
```

Never identify the merchant from:

* customer email
* customer phone
* payment amount
* payment description
* arbitrary metadata
* frontend-provided values

The provider account identity must be the authoritative boundary.

Razorpay's partner OAuth model exposes the sub-merchant account ID, and its partner webhook APIs are associated with a specific `account_id`.

---

# 19. Webhook Idempotency

Webhook delivery is not guaranteed to happen exactly once.

Razorpay documents that duplicate webhook deliveries can occur and provides:

```text
x-razorpay-event-id
```

as a unique event identifier.

Therefore the database must have a uniqueness constraint such as:

```text
(provider, provider_event_id)
```

or, if provider semantics require it:

```text
provider_event_id
```

Do not process the same event twice.

Example:

```text
Event received
     ↓
Does event_id already exist?
     │
   ┌─┴─┐
  YES  NO
   │    │
 return persist
```

---

# 20. PaymentEvent Model

Create a persistent event table.

Suggested schema:

```text
PaymentEvent
-------------------------
id
merchant_id
provider
provider_event_id
event_type
provider_payment_id
amount
currency
customer_reference
raw_payload
occurred_at
received_at
processed_at
created_at
```

For Phase 1, `raw_payload` is useful for debugging.

However:

* treat it as sensitive data
* restrict access
* never expose it through normal frontend APIs
* do not log sensitive payment information unnecessarily

---

# 21. Do Not Assume the Webhook Contains Everything

A webhook tells Voic that an event occurred and includes the provider-defined event payload.

Do not assume every piece of customer information will always be present.

The correct architecture is:

```text
Webhook
   ↓
Event says payment X failed
   ↓
Normalize known information
   ↓
If additional information is required:
   ↓
Use provider API with merchant's OAuth connection
   ↓
Fetch additional resource data
```

The provider integration layer owns this logic.

For example:

```python
async def get_payment_context(payment_id, connection):
    ...
```

The eventual normalized context might contain:

```text
payment_id
merchant_id
customer_id
customer_name
customer_email
customer_phone
amount
currency
failure_reason
```

But only populate fields that are legitimately available from the provider.

Do not fabricate missing information.

---

# 22. Payment Failure Event

The first business event we care about is:

```text
payment.failed
```

Razorpay documents `payment.failed` as a payment webhook event.

For Phase 1:

**Do not trigger a phone call when this event arrives.**

Instead:

```text
payment.failed
      ↓
persist event
      ↓
log successful processing
```

Later this will become:

```text
payment.failed
      ↓
eligibility engine
      ↓
RecoveryCase
      ↓
call
```

---

# 23. Intentional Test Failure

The developer must be able to intentionally generate a payment failure in Razorpay Test Mode.

Razorpay provides webhook testing in Test Mode, and the webhook payload structure is intended to match the corresponding live-mode structure.

The acceptance test is:

```text
Create/test payment
        ↓
Force failure
        ↓
Razorpay emits payment.failed
        ↓
Voic receives webhook
        ↓
Voic verifies signature
        ↓
Voic identifies merchant
        ↓
Voic stores PaymentEvent
        ↓
Developer can inspect database
```

Do not use real customer data during development.

---

# 24. Webhook Processing Strategy

The webhook endpoint should respond quickly.

Recommended:

```text
HTTP POST
   ↓
verify signature
   ↓
persist event
   ↓
return 2xx
```

Heavy processing should eventually happen asynchronously.

For Phase 1, simple synchronous persistence is acceptable.

Do not perform expensive provider API calls, AI calls, email sending, or phone calls inside the webhook request.

Razorpay expects successful webhook responses within a short response window and retries failed deliveries.

---

# 25. Webhook Events May Arrive Out of Order

Do not build business logic assuming:

```text
payment.authorized
    ↓
payment.captured
```

will always arrive in that exact order.

Razorpay explicitly documents that webhook events may arrive out of order.

For Phase 1 this mostly means:

* persist events independently
* don't assume ordering
* don't mutate state based solely on event arrival order

---

# 26. Webhook Configuration

Voic needs a webhook URL that Razorpay can reach.

Example:

```text
https://api.voic.example.com/api/webhooks/razorpay
```

Localhost cannot be used directly as a public webhook endpoint. Razorpay documents that webhook URLs must be publicly reachable and recommends HTTPS.

For local development, use a suitable public HTTPS development/staging endpoint or an approved tunneling solution.

Do not build the system around a permanent local tunnel.

---

# 27. Razorpay Webhook Creation

Where supported by the Razorpay partner integration, Voic should create/configure the merchant-specific webhook through Razorpay's API rather than asking every merchant to manually configure it.

Razorpay documents a partner webhook creation endpoint:

```text
POST /v2/accounts/:account_id/webhooks
```

with the merchant account ID, webhook URL, secret, and selected events.

For Phase 1, configure at minimum the event required to observe payment failures:

```text
payment.failed
```

Additional events can be added later when the recovery lifecycle requires them.

---

# 28. Important: Do Not Build Recovery Logic Yet

Do NOT implement:

```text
if payment.failed:
    call customer
```

Instead:

```text
if payment.failed:
    persist PaymentEvent
```

The future business rule will be something like:

```text
PaymentFailure
      ↓
Eligibility Rules
      ↓
RecoveryCase
```

The eventual eligibility rules may include:

```text
amount >= merchant.minimum_recovery_amount
AND customer has phone
AND failure type is recoverable
AND payment isn't already recovered
AND customer hasn't exceeded call limit
AND merchant allows calls at this time
AND other merchant-configured criteria
```

But those rules belong to a later phase.

---

# 29. Future Recovery Architecture

The architecture should eventually evolve into:

```text
PaymentEvent
     ↓
Eligibility Engine
     ↓
RecoveryCase
     ↓
Call Orchestrator
     ↓
Voice Agent
     ↓
Conversation Outcome
     ↓
Optional Checkout Link
     ↓
Customer Payment
     ↓
Payment Event
     ↓
Attribution
     ↓
Recovered
```

The voice agent must not become the system of record.

---

# 30. Future Voice Agent Context

Eventually, the voice agent will receive a Voic-owned context object.

Example:

```json
{
  "recovery_case_id": "rc_123",
  "customer": {
    "name": "Rahul",
    "phone": "+91..."
  },
  "payment": {
    "amount": 5000,
    "currency": "INR"
  },
  "failure": {
    "category": "payment_failed"
  }
}
```

The agent should NOT receive:

* card numbers
* CVV
* bank credentials
* UPI PIN
* passwords
* OTPs
* other sensitive authentication information

The call should never ask the customer to disclose such information.

This is a fundamental product/security constraint.

---

# 31. Future Payment Recovery

The eventual recovery flow is:

```text
Customer:
"I had some problem making the payment."

Agent:
"Would you like me to send you a fresh payment link?"

Customer:
"Yes."

Agent
   ↓
Voic backend
   ↓
generate/retrieve legitimate checkout/payment link
   ↓
email customer
```

The LLM should not directly manufacture payment URLs.

The backend/payment-provider integration should own payment-link creation.

---

# 32. Future Recovery Attribution

Eventually Voic must be able to answer:

> "Why does Voic consider this payment recovered because of this call?"

Therefore future models should establish a deterministic chain:

```text
PaymentFailure
      ↓
RecoveryCase
      ↓
Call
      ↓
CheckoutLink
      ↓
SuccessfulPayment
```

The LLM must not decide whether money was recovered.

Payment recovery should be established using provider-side payment evidence and Voic's own identifiers/relationships.

---

# 33. Authentication

Implement basic secure merchant authentication.

The exact authentication mechanism can be selected by the implementation agent, but it must satisfy:

* secure password hashing if passwords are used
* secure session/token handling
* authenticated backend endpoints
* merchant-level authorization
* no cross-merchant data access

Every protected request must resolve to:

```text
authenticated user
        ↓
merchant
        ↓
resource
```

Never trust a `merchant_id` supplied by the frontend without checking ownership.

---

# 34. Multi-Tenant Security

This is critical.

Every merchant-owned database query must be scoped by merchant.

Bad:

```python
PaymentEvent.get(id=event_id)
```

Better:

```python
PaymentEvent.get(
    id=event_id,
    merchant_id=current_merchant.id
)
```

The backend must enforce tenant isolation.

Merchant A must never be able to retrieve Merchant B's:

* provider connections
* payment events
* customer data
* webhook payloads
* future recovery cases
* future call records

---

# 35. Frontend Pages

Create a minimal frontend.

### `/`

Landing/login routing.

### `/login`

Login page.

### `/signup`

Merchant signup.

### `/dashboard`

Basic merchant dashboard.

For Phase 1:

```text
Connected Providers
-------------------

Razorpay
Status: Connected

Recent Payment Events
---------------------

payment.failed
₹5,000
Received: ...
```

This does not need to be a polished analytics dashboard.

Its purpose is to demonstrate that the integration works.

---

# 36. Integration UI

Create a page such as:

```text
/settings/integrations
```

Display:

```text
Payment Providers

Razorpay
[ Connect Razorpay ]

Status:
Connected
```

After connection:

```text
Razorpay
Connected

Account:
Connected Razorpay account

Webhook:
Configured

Last webhook:
2 minutes ago
```

Do not expose:

* access token
* refresh token
* webhook secret
* OAuth client secret

---

# 37. Developer Debugging

During Phase 1, provide a way for the developer to verify integration health.

Possible dashboard:

```text
Integration Health

Razorpay
--------------------
OAuth:          ✓
Account:        ✓
Webhook:        ✓
Signature:      ✓
Last Event:     payment.failed
Last Event At:  ...
```

And:

```text
Recent Events

ID             Type             Payment ID
evt_xxx        payment.failed   pay_xxx
```

Do not display full raw webhook payload to normal merchant users.

If a developer-only debug endpoint is implemented, protect it appropriately.

---

# 38. Database Constraints

At minimum:

### User

```text
email UNIQUE
```

### Merchant

appropriate ownership relationship.

### ProviderConnection

Prefer:

```text
UNIQUE(merchant_id, provider)
```

if only one connection per provider is supported.

### PaymentEvent

```text
UNIQUE(provider, provider_event_id)
```

This is essential for webhook idempotency.

---

# 39. Logging Requirements

Logs should help diagnose the integration without leaking secrets.

Good:

```text
Razorpay OAuth completed
merchant_id=merch_123
provider_account_id=acc_xxx
```

Good:

```text
Received Razorpay webhook
event_type=payment.failed
event_id=evt_xxx
merchant_id=merch_123
```

Bad:

```text
access_token=ey...
refresh_token=...
webhook_secret=...
```

Never log credentials.

Be cautious about logging:

* customer phone
* customer email
* payment metadata
* full webhook payload

---

# 40. Error Handling

OAuth failures should be represented cleanly.

Examples:

```text
OAUTH_STATE_MISMATCH
OAUTH_ACCESS_DENIED
OAUTH_TOKEN_EXCHANGE_FAILED
OAUTH_PROVIDER_ERROR
```

Webhook failures:

```text
WEBHOOK_INVALID_SIGNATURE
WEBHOOK_UNKNOWN_MERCHANT
WEBHOOK_DUPLICATE
WEBHOOK_INVALID_PAYLOAD
```

Do not return implementation details or secrets to the browser.

---

# 41. Testing Requirements

The agent must write automated tests.

Minimum tests:

## Authentication

```text
signup works
login works
invalid credentials fail
```

## OAuth

```text
OAuth state generated
OAuth state validated
invalid state rejected
OAuth callback exchanges code
tokens stored encrypted
tokens never returned in API response
```

## Token refresh

```text
expired token triggers refresh
new access token stored
new refresh token stored
old refresh token is replaced
```

## Webhooks

```text
valid signature accepted
invalid signature rejected
malformed payload rejected
duplicate event ignored
unknown merchant rejected
payment.failed persisted
```

## Tenant isolation

```text
Merchant A cannot access Merchant B's events
Merchant A cannot access Merchant B's provider connection
```

---

# 42. Acceptance Test

The phase is considered complete only when this exact scenario works.

### Step 1

Create a Voic account.

```text
User
  ↓
Merchant
```

### Step 2

Click:

```text
Connect Razorpay
```

### Step 3

Complete Razorpay OAuth authorization.

### Step 4

Voic receives the callback.

### Step 5

Voic securely stores:

```text
provider = razorpay
razorpay_account_id
access_token
refresh_token
expiry
scopes
```

### Step 6

Voic configures the webhook.

### Step 7

Create an intentional test payment failure in Razorpay Test Mode.

### Step 8

Razorpay sends:

```text
payment.failed
```

### Step 9

Voic receives the webhook.

### Step 10

Voic verifies:

```text
X-Razorpay-Signature
```

against the raw request body.

### Step 11

Voic identifies the merchant.

### Step 12

Voic persists:

```text
PaymentEvent
```

### Step 13

The developer can see the event in the database/dashboard.

The complete test should look like:

```text
                 ┌───────────────┐
                 │   Merchant    │
                 └───────┬───────┘
                         │
                       OAuth
                         │
                         ▼
                 ┌───────────────┐
                 │    Voic       │
                 │   Backend     │
                 └───────┬───────┘
                         │
                    webhook setup
                         │
                         ▼
                 ┌───────────────┐
                 │   Razorpay    │
                 └───────┬───────┘
                         │
                   test payment
                         │
                       FAIL
                         │
                         ▼
                 payment.failed
                         │
                         ▼
                 ┌───────────────┐
                 │ Voic Webhook  │
                 └───────┬───────┘
                         │
                  verify signature
                         │
                         ▼
                 identify merchant
                         │
                         ▼
                 persist event
                         │
                         ▼
                 ┌───────────────┐
                 │ PaymentEvent  │
                 └───────────────┘
```

---

# 43. Explicitly Out of Scope

Do NOT implement these in Phase 1:

### Voice

* ElevenLabs
* Vobiz
* SIP
* phone calls
* STT
* TTS
* voice-agent prompts
* Hinglish conversation
* LangGraph

### Recovery

* RecoveryCase
* eligibility engine
* call scheduling
* retries
* customer calling
* call outcomes

### Email

* email domain configuration
* SMTP
* Resend/SendGrid/etc.
* email templates
* sending checkout links

### Payment Recovery

* payment-link generation
* checkout generation
* recovered-money attribution
* recovery analytics

### AI

* LLM
* agent orchestration
* tool calling
* conversation memory

These belong to later phases.

---

# 44. Future Architecture Boundary

The eventual system should evolve toward:

```text
                     ┌────────────────────┐
                     │   Payment Provider  │
                     └──────────┬─────────┘
                                │
                         OAuth / Webhooks
                                │
                                ▼
                     ┌────────────────────┐
                     │   Voic Backend     │
                     │                    │
                     │ Payment Events     │
                     │ Recovery Cases     │
                     │ Merchant State     │
                     └──────────┬─────────┘
                                │
                         Orchestration
                                │
                                ▼
                     ┌────────────────────┐
                     │   Voice Agent      │
                     │                    │
                     │ STT                │
                     │ LLM                │
                     │ TTS                │
                     └──────────┬─────────┘
                                │
                         actions/tools
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
            Email          Payment API       Other tools
               │                │
               └────────┬───────┘
                        ▼
                 Customer Payment
                        │
                        ▼
                 Payment Provider
                        │
                        ▼
                  Voic Webhook
```

The backend remains the source of truth.

---

# 45. Implementation Philosophy

Do not over-engineer Phase 1.

The objective is not to create the final Voic architecture.

The objective is to establish a trustworthy foundation:

```text
Identity
+
Merchant boundary
+
OAuth
+
Secure credentials
+
Webhook verification
+
Event persistence
```

Build these correctly before adding AI.

When implementing something provider-specific, isolate it behind a provider abstraction.

When implementing something security-sensitive, prefer explicit code and tests over clever abstractions.

When unsure about a provider behavior, consult the current provider documentation rather than guessing.

---

# 46. Current Razorpay Constraints to Respect

The implementation must account for the following currently documented behavior:

* Razorpay OAuth is intended for technology partners accessing sub-merchant accounts.
* OAuth uses an authorization-code flow.
* OAuth returns an access token, refresh token, and `razorpay_account_id`.
* Access tokens are currently documented as expiring after 90 days.
* Refreshing an access token returns a new refresh token, so refresh-token rotation must be handled correctly.
* Razorpay webhook signatures use HMAC-SHA256 over the raw request body.
* Duplicate webhook delivery is possible and must be handled idempotently.
* Webhooks can arrive out of order.
* Webhooks require a publicly reachable endpoint; localhost cannot directly receive provider webhook delivery.
* Razorpay provides Test Mode for testing webhook behavior.

These are integration facts, not assumptions.

---

# 47. Definition of Done

Phase 1 is DONE when:

* [ ] Next.js application runs.
* [ ] Python/FastAPI backend runs.
* [ ] PostgreSQL database is configured.
* [ ] Database migrations work.
* [ ] User signup works.
* [ ] User login works.
* [ ] Merchant is created/associated correctly.
* [ ] Razorpay OAuth connection can be initiated.
* [ ] OAuth `state` validation is implemented.
* [ ] Razorpay authorization callback works.
* [ ] OAuth tokens are stored securely.
* [ ] Razorpay account ID is stored.
* [ ] Access-token expiration is stored.
* [ ] Refresh-token rotation works.
* [ ] Razorpay webhook is configured.
* [ ] Public webhook endpoint exists.
* [ ] Webhook signature is verified against the raw request body.
* [ ] Merchant is identified from the provider account boundary.
* [ ] Duplicate webhook events are safely ignored.
* [ ] `payment.failed` is persisted.
* [ ] Raw payload is retained securely for debugging.
* [ ] Merchant isolation is enforced.
* [ ] Automated tests cover OAuth, token storage, webhook validation, idempotency, and tenant isolation.
* [ ] A test payment failure can be intentionally triggered.
* [ ] The resulting `payment.failed` event appears in the Voic database/dashboard.

Once all of these work, **stop Phase 1**.

Do not proceed to the voice agent until this foundation has been validated.
