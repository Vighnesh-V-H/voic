# VOIC — Stripe Connect Payment Integration

## 1. Goal

Allow a VOIC merchant to connect their Stripe account and allow VOIC to:

* Access the merchant's existing Stripe products.
* Create/manage payments for the merchant.
* Create Stripe Payment Links when required.
* Receive payment success/failure events through webhooks.
* Keep VOIC payment status synchronized with Stripe.

All development and testing will initially use the **Stripe Sandbox/Test environment**.

---

## 2. Merchant Connection

The merchant connects Stripe to VOIC using Stripe Connect.

```text
Merchant
   ↓
Connect Stripe
   ↓
Stripe authorization
   ↓
VOIC stores connected account
```

Store the connected Stripe account ID against the VOIC merchant.

```text
ProviderConnection
- merchant_id
- provider = STRIPE
- provider_account_id
- status
```

---

## 3. Products

After connecting Stripe, VOIC can retrieve the merchant's existing Stripe products and prices.

```text
VOIC
  ↓
Stripe Connect API
  ↓
Merchant's Stripe account
  ↓
Products + Prices
```

VOIC should store the Stripe product/price IDs when needed rather than duplicating the entire Stripe catalog.

---

## 4. Payment Flow

When a payment needs to be created:

```text
Merchant / VOIC
      ↓
Select Stripe Product/Price
      ↓
Create Payment / Payment Link
      ↓
Stripe
      ↓
Customer
      ↓
Payment
```

The payment should be associated with:

```text
VOIC merchant_id
Stripe connected account ID
Stripe product/price ID
Stripe payment/payment-link ID
```

---

## 5. Webhooks

VOIC exposes a centralized Stripe webhook:

```text
POST /api/v1/webhooks/stripe
```

Stripe Connect sends events for connected accounts to VOIC.

Important events include:

```text
payment_intent.succeeded
payment_intent.payment_failed
```

VOIC should:

1. Verify the webhook signature.
2. Identify the connected Stripe account from the signed event envelope (`account`, or top-level `context` in newer API versions) and resolve it to exactly one VOIC merchant. Never use metadata or other payload values to select the merchant; an event with a missing account/context is rejected.
3. Find the corresponding VOIC payment (metadata `voic_payment_id` correlation, scoped to the resolved merchant).
4. Update its status.
5. Store the Stripe event ID to prevent duplicate processing.

Deauthorization (`account.application.deauthorized`) and merchant-initiated disconnect delete the merchant's VOIC-owned Stripe data (connections, payments, events) after explicit merchant confirmation; the merchant stays signed in.

Example:

```text
Stripe
   ↓
payment_intent.payment_failed
   ↓
VOIC webhook
   ↓
Find merchant/payment
   ↓
Payment = FAILED
```

---

## 6. Payment Status

VOIC maintains its own payment status:

```text
CREATED
PENDING
COMPLETED
FAILED
CANCELLED
```

Stripe webhook events are the source of truth for the final payment state.

---

## 7. API Endpoints

### Stripe

```text
GET /api/v1/stripe/connect
GET /api/v1/stripe/callback
DELETE /api/v1/stripe/connection
```

### Products

```text
GET /api/v1/stripe/products
GET /api/v1/stripe/products/:id
```

### Payments

```text
POST /api/v1/payments
GET /api/v1/payments/:id
```

### Payment Links

```text
POST /api/v1/payment-links
GET /api/v1/payment-links/:id
```

### Webhook

```text
POST /api/v1/webhooks/stripe
```

---

## 8. End-to-End Flow

```text
1. Merchant connects Stripe
          ↓
2. VOIC stores connected account
          ↓
3. VOIC retrieves merchant's products/prices
          ↓
4. Merchant selects a product
          ↓
5. VOIC creates payment/payment link
          ↓
6. Customer pays through Stripe
          ↓
7. Stripe sends webhook
          ↓
8. VOIC verifies event
          ↓
9. VOIC updates payment status
```

## 9. Initial Scope

Build and test everything in **Stripe Sandbox/Test mode** first:

* Stripe Connect
* Connected merchant
* Product retrieval
* Payment creation
* Payment Links
* Successful payment
* Failed payment
* Webhook handling
* Payment status synchronization

Production Stripe credentials and real payments are out of scope for the initial implementation.
