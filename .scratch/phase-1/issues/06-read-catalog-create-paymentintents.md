# 06: Read Stripe catalog and create PaymentIntents

> Synced from https://github.com/Vighnesh-V-H/voic/issues/6
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-03T12:54:02Z | Updated: 2026-09-03T12:54:02Z
> Parent: #4 | Blocked by: #5

**What to build:** A connected merchant can browse the products and prices owned by Stripe and create a Voic-owned PaymentIntent from an existing one-time price.

**Blocked by:** #5

**Status:** ready-for-agent

- [ ] Authenticated catalog endpoints list and retrieve products/prices from the current merchant's connected Stripe account.
- [ ] Catalog responses expose only the fields needed for selection and never expose platform credentials.
- [ ] Product creation is not offered by Voic; Stripe remains the catalog source of truth.
- [ ] An authenticated merchant can create a Payment from an existing one-time price and quantity.
- [ ] The backend validates that the selected price belongs to the merchant's connected account and is eligible for this flow.
- [ ] The backend creates a Stripe PaymentIntent in the connected account and stores the Voic Payment with provider IDs, price ID, amount, currency, and initial status.
- [ ] The PaymentIntent contains a non-sensitive Voic payment identifier in metadata.
- [ ] The response may expose the Stripe client secret for client-side confirmation but never exposes platform secrets or OAuth credentials.
- [ ] Payment retrieval is scoped to the authenticated merchant.
- [ ] Automated tests cover catalog scoping, invalid prices, PaymentIntent creation, metadata, response safety, and cross-merchant access.

## Full body

## Parent

Part of #4.

## What to build

A connected merchant can browse the products and prices owned by Stripe and create a Voic-owned PaymentIntent from an existing one-time price.

## Acceptance criteria

- [ ] Authenticated catalog endpoints list and retrieve products/prices from the current merchant's connected Stripe account.
- [ ] Catalog responses expose only the fields needed for selection and never expose platform credentials.
- [ ] Product creation is not offered by Voic; Stripe remains the catalog source of truth.
- [ ] An authenticated merchant can create a Payment from an existing one-time price and quantity.
- [ ] The backend validates that the selected price belongs to the merchant's connected account and is eligible for this flow.
- [ ] The backend creates a Stripe PaymentIntent in the connected account and stores the Voic Payment with provider IDs, price ID, amount, currency, and initial status.
- [ ] The PaymentIntent contains a non-sensitive Voic payment identifier in metadata.
- [ ] The response may expose the Stripe client secret for client-side confirmation but never exposes platform secrets or OAuth credentials.
- [ ] Payment retrieval is scoped to the authenticated merchant.
- [ ] Automated tests cover catalog scoping, invalid prices, PaymentIntent creation, metadata, response safety, and cross-merchant access.

## Blocked by

- #5
