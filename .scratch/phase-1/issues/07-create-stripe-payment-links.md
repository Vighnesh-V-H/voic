# 07: Create Stripe Payment Links from existing prices

> Synced from https://github.com/Vighnesh-V-H/voic/issues/7
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-03T12:54:15Z | Updated: 2026-09-03T12:54:15Z
> Parent: #4 | Blocked by: #6

**What to build:** A connected merchant can create and retrieve a Stripe-hosted Payment Link from an existing one-time Stripe price, with a Voic-owned Payment tracking the link and its eventual payment.

**Blocked by:** #6

**Status:** ready-for-agent

- [ ] An authenticated merchant can create a Payment Link from an existing one-time price and quantity.
- [ ] The backend validates that the price belongs to the merchant's connected Stripe account and is eligible for a one-time Payment Link.
- [ ] The backend creates the Payment Link in the connected account and stores its provider ID and hosted URL on a Voic Payment.
- [ ] The Payment Link metadata contains the Voic payment identifier.
- [ ] The Payment Link's `payment_intent_data.metadata` contains the same identifier for generated PaymentIntents.
- [ ] The response returns the hosted URL and safe payment details without secrets.
- [ ] Payment Link retrieval is scoped to the authenticated merchant.
- [ ] The frontend can request a link and present the Stripe-hosted URL without constructing it.
- [ ] Automated tests cover creation, metadata propagation inputs, invalid prices, response safety, and tenant isolation.

## Full body

## Parent

Part of #4.

## What to build

A connected merchant can create and retrieve a Stripe-hosted Payment Link from an existing one-time Stripe price, with a Voic-owned Payment tracking the link and its eventual payment.

## Acceptance criteria

- [ ] An authenticated merchant can create a Payment Link from an existing one-time price and quantity.
- [ ] The backend validates that the price belongs to the merchant's connected Stripe account and is eligible for a one-time Payment Link.
- [ ] The backend creates the Payment Link in the connected account and stores its provider ID and hosted URL on a Voic Payment.
- [ ] The Payment Link metadata contains the Voic payment identifier.
- [ ] The Payment Link's `payment_intent_data.metadata` contains the same identifier for generated PaymentIntents.
- [ ] The response returns the hosted URL and safe payment details without secrets.
- [ ] Payment Link retrieval is scoped to the authenticated merchant.
- [ ] The frontend can request a link and present the Stripe-hosted URL without constructing it.
- [ ] Automated tests cover creation, metadata propagation inputs, invalid prices, response safety, and tenant isolation.

## Blocked by

- #6
