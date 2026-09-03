# 09: Expose the complete Stripe integration in the merchant frontend

> Synced from https://github.com/Vighnesh-V-H/voic/issues/9
> State: OPEN | Labels: ready-for-agent | Created: 2026-09-03T12:54:37Z | Updated: 2026-09-03T12:54:37Z
> Parent: #4 | Blocked by: #8

**What to build:** The authenticated frontend exposes the complete Stripe integration workflow and gives a developer enough visibility to validate a Stripe Test Mode payment failure from connection through synchronized Payment status.

**Blocked by:** #8

**Status:** ready-for-agent

- [ ] The integration settings view lets a merchant start Stripe connection and displays connection state after OAuth.
- [ ] The merchant can browse Stripe products and prices from the connected account.
- [ ] The merchant can create a PaymentIntent or Payment Link from an eligible existing price.
- [ ] Payment Link URLs are presented as Stripe-hosted links and are never assembled by frontend code.
- [ ] The dashboard shows safe payment details, current Payment status, and recent PaymentEvents for the current merchant.
- [ ] The UI never displays platform secrets, OAuth credentials, webhook secrets, or unrestricted raw webhook payloads.
- [ ] Loading, OAuth failure, disconnected, invalid selection, and provider error states are represented clearly.
- [ ] The frontend uses the existing authenticated API/session conventions and cannot access another merchant's resources.
- [ ] A documented manual Test Mode flow uses Stripe CLI or a temporary public HTTPS endpoint to forward a Connect payment failure.
- [ ] The complete flow demonstrates OAuth connection, catalog retrieval, payment or link creation, webhook verification, event persistence, and final Payment status synchronization.
- [ ] Frontend lint and build pass, and backend automated tests pass.

## Full body

## Parent

Part of #4.

## What to build

The authenticated frontend exposes the complete Stripe integration workflow and gives a developer enough visibility to validate a Stripe Test Mode payment failure from connection through synchronized Payment status.

## Acceptance criteria

- [ ] The integration settings view lets a merchant start Stripe connection and displays connection state after OAuth.
- [ ] The merchant can browse Stripe products and prices from the connected account.
- [ ] The merchant can create a PaymentIntent or Payment Link from an eligible existing price.
- [ ] Payment Link URLs are presented as Stripe-hosted links and are never assembled by frontend code.
- [ ] The dashboard shows safe payment details, current Payment status, and recent PaymentEvents for the current merchant.
- [ ] The UI never displays platform secrets, OAuth credentials, webhook secrets, or unrestricted raw webhook payloads.
- [ ] Loading, OAuth failure, disconnected, invalid selection, and provider error states are represented clearly.
- [ ] The frontend uses the existing authenticated API/session conventions and cannot access another merchant's resources.
- [ ] A documented manual Test Mode flow uses Stripe CLI or a temporary public HTTPS endpoint to forward a Connect payment failure.
- [ ] The complete flow demonstrates OAuth connection, catalog retrieval, payment or link creation, webhook verification, event persistence, and final Payment status synchronization.
- [ ] Frontend lint and build pass, and backend automated tests pass.

## Blocked by

- #8
