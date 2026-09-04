# 20: Persist call attempts with one-call-per-payment dedupe

> Synced from https://github.com/Vighnesh-V-H/voic/issues/20
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-04T09:08:42Z | Updated: 2026-09-04T09:08:42Z
> Blocked by: #18

**What to build:** Every placed recovery call is recorded, so a payment is never dialed twice no matter how often Stripe retries the failure webhook, and a later payment success stops further attempts.

**Blocked by:** #18

**Status:** ready-for-agent

- [ ] Call attempts persist with merchant, payment, provider call id, status, and timestamps.
- [ ] Repeat FAILED webhooks for the same payment place exactly one call.
- [ ] A COMPLETED transition for the payment prevents or closes further attempts.
- [ ] Database migration included.
- [ ] Automated tests cover duplicates, out-of-order events, and cross-merchant isolation.

## Full body

## What to build

Every placed recovery call is recorded, so a payment is never dialed twice no matter how often Stripe retries the failure webhook, and a later payment success stops further attempts.

## Acceptance criteria

- [ ] Call attempts persist with merchant, payment, provider call id, status, and timestamps.
- [ ] Repeat FAILED webhooks for the same payment place exactly one call.
- [ ] A COMPLETED transition for the payment prevents or closes further attempts.
- [ ] Database migration included.
- [ ] Automated tests cover duplicates, out-of-order events, and cross-merchant isolation.

## Blocked by

- #18
