# VOIC — PayPal Payments Spec

## 1. Goal

Allow a VOIC user to:

1. Connect their PayPal account to VOIC using OAuth.
2. Configure products/services they want to receive payments for.
3. Initiate payments through PayPal.
4. Let the customer complete payment using PayPal's payment experience.
5. Receive PayPal webhook events in VOIC.
6. Keep VOIC's internal payment status synchronized with PayPal.

**Core principle:**

> PayPal handles the actual payment. VOIC handles merchant connections, payment records, and payment-state reconciliation.

---

# 2. Architecture

```text
                    VOIC
              ┌──────┴──────┐
              │             │
          Merchant       Payments DB
              │             │
              │             ↑
              ↓             │
           PayPal ───────────┘
              │
              ↓
           Customer
```

VOIC should not depend on having its own checkout UI.

PayPal remains the payment provider and can provide the customer-facing payment experience.

---

# 3. PayPal OAuth

A VOIC merchant connects their PayPal account.

```text
Merchant
   ↓
Connect PayPal
   ↓
PayPal OAuth
   ↓
Merchant authorizes VOIC
   ↓
PayPal callback
   ↓
VOIC stores PayPal connection
```

VOIC should associate the PayPal account with the VOIC merchant.

Example:

```text
ProviderConnection

- id
- merchant_id
- provider = PAYPAL
- provider_account_id
- access_token / token reference
- refresh_token / token reference
- status
- created_at
- updated_at
```

There should be only one active PayPal connection for a merchant.

The PayPal account identifier should also be unique across connections.

---

# 4. Product

A merchant can create products/services inside VOIC.

Example:

```text
Product

- id
- merchant_id
- name
- description
- amount
- currency
- status
```

Example:

```text
Name: Consultation
Amount: ₹500
Currency: INR
```

The product is a VOIC concept. It does not necessarily need to be created as a permanent PayPal product/catalog item.

---

# 5. Payment

A **Payment** is the central VOIC object.

Example:

```text
Payment

- id
- merchant_id
- product_id
- amount
- currency

- provider = PAYPAL
- paypal_order_id
- paypal_capture_id

- status
- failure_reason

- created_at
- updated_at
```

Possible statuses:

```text
CREATED
PENDING
COMPLETED
FAILED
CANCELLED
```

The payment record connects:

```text
VOIC Merchant
      ↓
VOIC Product
      ↓
VOIC Payment
      ↓
PayPal Order
      ↓
PayPal Capture
```

---

# 6. Payment Initiation

When a customer needs to pay, VOIC creates a payment and a corresponding PayPal Order for the merchant's connected PayPal account.

```text
VOIC
  ↓
Create Payment
  ↓
Identify merchant
  ↓
Find merchant's PayPal connection
  ↓
Create PayPal Order
  ↓
Store paypal_order_id
  ↓
Return PayPal approval/payment URL
```

The PayPal Order should be created **per payment attempt**.

Do not create one permanent PayPal checkout/order and reuse it for every customer.

---

# 7. Customer Checkout

The customer should ultimately complete the payment through PayPal.

Example:

```text
Merchant
   ↓
VOIC
   ↓
Payment created
   ↓
PayPal Order created
   ↓
PayPal checkout/approval URL
   ↓
Customer
   ↓
PayPal login/payment
```

VOIC does not need to reproduce PayPal's payment UI.

A VOIC-hosted payment page can be added later if required, but it is not a dependency of the initial architecture.

---

# 8. Capture

After the customer approves the PayPal payment, VOIC captures the PayPal Order where required by the PayPal Checkout flow.

```text
Customer approves
       ↓
VOIC
       ↓
Capture PayPal Order
       ↓
PayPal
       ↓
Capture result
```

VOIC stores the resulting:

```text
paypal_order_id
paypal_capture_id
```

However, the frontend response should **not be treated as the final source of truth** for payment status.

---

# 9. PayPal Webhooks

VOIC should expose one centralized PayPal webhook endpoint.

```text
POST /webhooks/paypal
```

Example:

```text
PayPal
   ↓
POST /webhooks/paypal
   ↓
VOIC
   ↓
Identify payment
   ↓
Update payment status
```

PayPal sends events such as successful, pending, denied, or other relevant payment/order events.

The webhook handler should:

1. Verify the webhook authenticity/signature.
2. Read the PayPal event type.
3. Extract the relevant PayPal order/capture/payment identifier.
4. Find the corresponding VOIC payment.
5. Update the payment state.
6. Store the webhook event for auditing/idempotency.
7. Return a successful response to PayPal.

---

# 10. Webhook Events

At minimum, the implementation should handle the relevant PayPal events for:

```text
Payment completed
Payment denied/failed
Payment pending
Order completed
Refunds
Disputes/chargebacks
```

The exact event subscriptions should be finalized based on the PayPal APIs/products enabled for VOIC.

For example:

```text
PAYMENT.CAPTURE.COMPLETED
        ↓
Payment = COMPLETED
```

and:

```text
PAYMENT.CAPTURE.DENIED
        ↓
Payment = FAILED
```

Webhook events should be stored so that duplicate webhook deliveries do not result in duplicate processing.

---

# 11. Webhook Idempotency

PayPal may deliver the same webhook more than once.

VOIC should therefore maintain something like:

```text
PaymentWebhookEvent

- id
- provider = PAYPAL
- paypal_event_id
- event_type
- payment_id
- payload
- processed_at
```

Add a uniqueness constraint on:

```text
(provider, paypal_event_id)
```

Processing should be idempotent.

Example:

```text
Webhook #123
     ↓
Process
     ↓
Payment = COMPLETED

Webhook #123 again
     ↓
Already processed
     ↓
Ignore safely
```

---

# 12. Payment Failure Handling

A failed PayPal payment should not require the customer frontend to tell VOIC that the payment failed.

Instead:

```text
Customer
   ↓
PayPal
   ↓
Payment fails
   ↓
PayPal webhook
   ↓
VOIC
   ↓
Payment.status = FAILED
```

VOIC can then expose the status through:

```text
GET /payments/:payment_id
```

or notify the relevant merchant/VOIC workflow.

This is particularly important for VOIC because payment state may need to trigger other actions, such as:

```text
Payment failed
     ↓
VOIC agent/workflow
     ↓
Contact customer
     ↓
Retry payment / notify merchant
```

---

# 13. Multiple Merchants

VOIC uses a **single PayPal webhook endpoint** for all connected merchants.

Example:

```text
Merchant A ─┐
Merchant B ─┤
Merchant C ─┼──→ PayPal
Merchant D ─┘      │
                   ↓
             VOIC webhook
                   │
                   ↓
          Identify PayPal payment
                   │
                   ↓
             VOIC Payment
                   │
                   ↓
              Merchant
```

There should not be a separate webhook endpoint for every merchant.

The internal payment record determines which VOIC merchant owns the payment.

---

# 14. Payment Link — Optional

A VOIC payment link can still be supported, but it should **not be the foundation of the payment architecture**.

Example:

```text
https://voic.app/pay/pl_123
```

The link references:

```text
PaymentLink
- id
- merchant_id
- product_id
- amount
- currency
- status
```

When the customer opens the link:

```text
VOIC Payment Link
       ↓
Create Payment
       ↓
Create PayPal Order
       ↓
Customer goes to PayPal
```

This allows VOIC to offer payment links without making VOIC itself the payment processor.

---

# 15. API Endpoints

### PayPal connection

```text
GET  /paypal/connect
GET  /paypal/callback
DELETE /paypal/connection
```

### Products

```text
POST   /products
GET    /products
GET    /products/:id
PATCH  /products/:id
DELETE /products/:id
```

### Payments

```text
POST /payments
GET  /payments/:id
POST /payments/:id/capture
```

### Payment links — optional

```text
POST   /payment-links
GET    /payment-links/:id
DELETE /payment-links/:id
GET    /pay/:payment_link_id
```

### Webhook

```text
POST /webhooks/paypal
```

---

# 16. End-to-End Flow

```text
1. Merchant creates VOIC account
                ↓
2. Merchant connects PayPal through OAuth
                ↓
3. VOIC stores PayPal merchant connection
                ↓
4. Merchant creates product/service
                ↓
5. Customer needs to pay
                ↓
6. VOIC creates internal Payment
                ↓
7. VOIC creates PayPal Order for merchant
                ↓
8. Customer completes payment through PayPal
                ↓
9. VOIC captures the payment where required
                ↓
10. PayPal sends webhook
                ↓
11. VOIC verifies webhook
                ↓
12. VOIC finds Payment
                ↓
13. VOIC updates payment status
                ↓
14. Merchant/workflow receives final result
```

---

# 17. Design Principles

### PayPal is the payment provider

VOIC does not attempt to replace PayPal's payment experience.

### VOIC owns the business context

VOIC knows:

```text
Who is the merchant?
What product was purchased?
How much was expected?
Which payment was created?
What is the current payment status?
```

### Webhooks are the reconciliation mechanism

The application should not rely exclusively on:

* frontend redirects
* customer callbacks
* browser state
* the initial PayPal API response

The webhook system should reconcile the final state.

### Payments are independent

Every customer payment gets its own VOIC Payment and corresponding PayPal transaction/order identifiers.

### Webhooks are centralized

One VOIC webhook endpoint handles events from PayPal and maps them back to the appropriate merchant/payment.

---

# 18. Initial Scope

For the first implementation, build only:

```text
✓ PayPal OAuth
✓ Store merchant PayPal connection
✓ Product creation
✓ Payment creation
✓ PayPal Order creation
✓ PayPal checkout/approval flow
✓ Payment capture
✓ PayPal webhook
✓ Webhook verification
✓ Webhook idempotency
✓ Payment status updates
```

Payment links can be added on top of this once the core payment flow is working.

---

## Final Architecture

```text
             ┌───────────────────┐
             │       VOIC        │
             │                   │
Merchant ───→│ PayPal OAuth      │
             │ Products          │
             │ Payments          │
             │ Webhooks          │
             └─────────┬─────────┘
                       │
                       │ API
                       ↓
                ┌─────────────┐
                │   PayPal    │
                └──────┬──────┘
                       │
                       ↓
                    Customer
                       │
                       │ payment
                       ↓
                    PayPal
                       │
                       │ webhook
                       ↓
             POST /webhooks/paypal
                       │
                       ↓
                    VOIC DB
                       │
                       ↓
              Payment = COMPLETED
                 or FAILED/PENDING
```

**The central idea is: OAuth connects the merchant, PayPal processes the money, and webhooks tell VOIC what actually happened.**
