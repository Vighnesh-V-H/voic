# ADR-0004: Account-Less Webhook Correlation and Invoice Handling

## Status

Accepted

## Context

Some delivery setups (dashboard endpoints not configured for connected
accounts, Stripe CLI forwarding without `--forward-connect-to`) deliver
Connect events without the signed `account`/`context` envelope that ADR-0002
relies on for merchant resolution. With the strict boundary alone, every such
event is rejected and the app cannot function in those setups.

Subscription-mode checkouts made this worse: recurring payments surface as
`invoice.*` and `customer.subscription.*` events, which carry no payment
metadata (the Voic payment ID lands on the Subscription object only, and
invoices do not inherit it). A metadata-based fallback therefore rescues
one-time payments but can never rescue recurring ones.

## Decision

1. When the signed envelope carries no connected account, the webhook resolves
   the merchant through Stripe-asserted provider references found in the event
   (`payment_link`, `subscription`, `invoice`, or payment-intent ID) matched
   against stored `Payment` rows. If no reference is stored, local development
   may use `STRIPE_WEBHOOK_ACCOUNT_ID` or a single connected account. Metadata
   is never consulted for merchant selection; the ADR-0002 invariant holds.
2. `checkout.session.completed` captures the subscription and initial invoice
   IDs onto the payment so later invoice events correlate. Only IDs shaped
   like real PaymentIntents (`pi_*`) are stored as the payment ID; session IDs
   (`cs_*`) are not.
3. `invoice.paid` / `invoice.payment_succeeded` and (new invoice-payment
   model) `invoice_payment.paid` synchronize payment status to `COMPLETED`;
   `invoice.payment_failed` / `invoice_payment.failed` synchronize to `FAILED`,
   under the same out-of-order guard as other events. The nested payment
   intent inside `invoice_payment` events is captured so the matching
   `payment_intent.*` event correlates too.
4. Account-less events that cannot resolve a merchant are rejected with 400 and
   logged with event id/type (never the raw payload, per ADR-0003). Once a
   merchant is resolved, the event is persisted even when it does not correlate
   to a Voic-created payment, allowing all payment events for the account to be
   observed. Event families that can never carry payment state
   (`payment_method.*`) are ack-and-dropped as `ignored` instead of 400-retrying
   when account-less.

## Consequences

- Webhooks work with and without the signed account envelope; the signed
  envelope remains the primary path whenever present. Account-less routing is
  rejected when it is ambiguous, so production multi-merchant deployments
  must use Connect delivery with `account`/`context`.
- Provider references are safe to correlate on: unlike metadata strings, they
  are Stripe-asserted facts about which provider object an event concerns, and
  each provider object belongs to exactly one connected account.
- Only one subscription per payment link is tracked (first captured wins). A
  link paid by multiple customers surfaces later subscriptions as logged 400s;
  a dedicated Subscription table is future work if that matters.
- A later cycle's `invoice.payment_failed` supersedes an earlier success,
  reflecting the latest known billing state.

## Alternatives considered

- Restoring the metadata fallback was rejected: metadata is a
  merchant-controlled string, so any Stripe-signed event without an account
  could select an arbitrary merchant's payment.
- Requiring Connect delivery and rejecting everything else was rejected: it
  leaves the app non-functional in common test setups with no graceful path.
