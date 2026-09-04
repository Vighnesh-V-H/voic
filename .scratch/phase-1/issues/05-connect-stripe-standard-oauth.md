# 05: Connect existing merchant Stripe accounts through Standard OAuth

> Synced from https://github.com/Vighnesh-V-H/voic/issues/5
> State: OPEN | Labels: ready-for-agent | Assignee: Vighnesh-V-H | Created: 2026-09-03T12:53:54Z | Updated: 2026-09-03T12:55:34Z
> Parent: #4 | Blocking: #6

**What to build:** A merchant can connect an existing Stripe Test Mode account from Voic and see the connection status after returning from Stripe.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] An authenticated merchant can start Stripe Standard OAuth.
- [ ] The callback requires a valid, unexpired, single-use state bound to the merchant.
- [ ] A successful callback stores the connected Stripe account ID, mode, scope, provider, and active status.
- [ ] Stripe OAuth credentials and the platform secret are never returned to the browser or logs.
- [ ] API calls are prepared to use the platform secret with the connected account ID.
- [ ] Reconnection updates the merchant's existing Stripe provider connection instead of creating a duplicate.
- [ ] Disconnect and deauthorization mark the connection unusable while preserving future historical records.
- [ ] The integration UI displays connected and disconnected states without secrets.
- [ ] Automated API tests use the fake provider seam and cover success, state mismatch, expiry, reuse, and tenant isolation.
- [ ] Database migration and configuration support Stripe Test Mode.

## Full body

## Parent

Part of #4.

## What to build

A merchant can connect an existing Stripe Test Mode account from Voic and see the connection status after returning from Stripe.

## Acceptance criteria

- [ ] An authenticated merchant can start Stripe Standard OAuth.
- [ ] The callback requires a valid, unexpired, single-use state bound to the merchant.
- [ ] A successful callback stores the connected Stripe account ID, mode, scope, provider, and active status.
- [ ] Stripe OAuth credentials and the platform secret are never returned to the browser or logs.
- [ ] API calls are prepared to use the platform secret with the connected account ID.
- [ ] Reconnection updates the merchant's existing Stripe provider connection instead of creating a duplicate.
- [ ] Disconnect and deauthorization mark the connection unusable while preserving future historical records.
- [ ] The integration UI displays connected and disconnected states without secrets.
- [ ] Automated API tests use the fake provider seam and cover success, state mismatch, expiry, reuse, and tenant isolation.
- [ ] Database migration and configuration support Stripe Test Mode.

## Blocked by

None (can start immediately).
