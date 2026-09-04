# 19: Answer URL serves the payment-recovery call flow

> Synced from https://github.com/Vighnesh-V-H/voic/issues/19
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-04T09:08:38Z | Updated: 2026-09-04T09:08:38Z
> Blocked by: #18

**What to build:** When a triggered Vobiz call connects, our public answer endpoint replies with the Voice XML flow that speaks the failed-payment reminder for that specific payment. The trigger passes a per-call answer URL carrying the payment context instead of one static URL.

**Blocked by:** #18

**Status:** ready-for-agent

- [ ] A public answer endpoint returns a valid Voice XML recovery flow for a known payment.
- [ ] An unknown payment context gets a safe fallback message, never an error dump or another merchant's data.
- [ ] Per-call answer URLs carry the payment context and are verified merchant-side; the static answer URL is no longer used for recovery calls.
- [ ] No secrets, raw payloads, or cross-merchant data in responses or logs.
- [ ] Automated tests cover the known/unknown payment paths, XML validity, and tenant isolation.

## Full body

## What to build

When a triggered Vobiz call connects, our public answer endpoint replies with the Voice XML flow that speaks the failed-payment reminder for that specific payment. The trigger passes a per-call answer URL carrying the payment context instead of one static URL.

## Acceptance criteria

- [ ] A public answer endpoint returns a valid Voice XML recovery flow for a known payment.
- [ ] An unknown payment context gets a safe fallback message, never an error dump or another merchant's data.
- [ ] Per-call answer URLs carry the payment context and are verified merchant-side; the static answer URL is no longer used for recovery calls.
- [ ] No secrets, raw payloads, or cross-merchant data in responses or logs.
- [ ] Automated tests cover the known/unknown payment paths, XML validity, and tenant isolation.

## Blocked by

- #18
