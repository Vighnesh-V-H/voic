# 21: Hangup callback records the call outcome

> Synced from https://github.com/Vighnesh-V-H/voic/issues/21
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-04T09:08:47Z | Updated: 2026-09-04T09:08:47Z
> Blocked by: #19, #20

**What to build:** When a recovery call ends, Vobiz posts our hangup callback and we store the outcome (answered/completed/failed, durations) against the matching call attempt, so the merchant can later see what happened to each call.

**Blocked by:** #19, #20

**Status:** ready-for-agent

- [ ] A public hangup endpoint authenticates the callback with the shared token and maps it to exactly one call attempt via the provider call id.
- [ ] Unknown call ids and malformed posts are logged and answered 200 without writes.
- [ ] Outcome and durations are persisted; repeated hangup posts for the same call are idempotent.
- [ ] Automated tests cover the happy path, unknown id, malformed body, and duplicates.

## Full body

## What to build

When a recovery call ends, Vobiz posts our hangup callback and we store the outcome (answered/completed/failed, durations) against the matching call attempt, so the merchant can later see what happened to each call.

## Acceptance criteria

- [ ] A public hangup endpoint authenticates the callback with the shared token and maps it to exactly one call attempt via the provider call id.
- [ ] Unknown call ids and malformed posts are logged and answered 200 without writes.
- [ ] Outcome and durations are persisted; repeated hangup posts for the same call are idempotent.
- [ ] Automated tests cover the happy path, unknown id, malformed body, and duplicates.

## Blocked by

- #19, #20
