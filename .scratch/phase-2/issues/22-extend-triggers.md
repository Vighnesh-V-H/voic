# 22: Trigger recovery calls for checkout and invoice failures

> Synced from https://github.com/Vighnesh-V-H/voic/issues/22
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-04T09:08:52Z | Updated: 2026-09-04T09:08:52Z
> Blocked by: #20

**What to build:** Abandoned checkouts and failed subscription renewals trigger the same single recovery call as failed PaymentIntents, reusing the dedupe from the persistence ticket.

**Blocked by:** #20

**Status:** ready-for-agent

- [ ] Expired/async-failed checkout sessions and failed invoice payments flip their payment to FAILED and trigger one call each when a customer phone is present.
- [ ] Charge failures still do not trigger on their own (the paired PaymentIntent event owns the call).
- [ ] Success events still never trigger; duplicate events still place exactly one call.
- [ ] Webhook allowlist and status transitions extended, with automated tests per event type.

## Full body

## What to build

Abandoned checkouts and failed subscription renewals trigger the same single recovery call as failed PaymentIntents, reusing the dedupe from the persistence ticket.

## Acceptance criteria

- [ ] Expired/async-failed checkout sessions and failed invoice payments flip their payment to FAILED and trigger one call each when a customer phone is present.
- [ ] Charge failures still do not trigger on their own (the paired PaymentIntent event owns the call).
- [ ] Success events still never trigger; duplicate events still place exactly one call.
- [ ] Webhook allowlist and status transitions extended, with automated tests per event type.

## Blocked by

- #20
