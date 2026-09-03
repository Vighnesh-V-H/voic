# ADR-0002: Stripe Standard OAuth and Platform Webhooks

## Status

Accepted

## Context

Voic must connect merchants' existing Stripe accounts, act on behalf of those accounts, and receive payment events for all connected accounts. Stripe's current OAuth reference marks returned OAuth access tokens as deprecated for API requests and recommends the platform secret key with the connected account ID in the `Stripe-Account` header. Stripe Connect webhooks are platform-level endpoints that identify the connected account in the event's top-level `account` field.

## Decision

Voic uses Stripe Standard OAuth to authorize an existing merchant Stripe account and stores the returned connected account ID, mode, scope, and connection status. Server-side Stripe API calls use the platform secret key and the connected account ID; OAuth access and refresh tokens are not persisted or returned.

Voic uses one platform-level Connect webhook endpoint configured with `connect=true` and a deployment-managed signing secret. Verified webhook events resolve the merchant through the event's connected account ID. PaymentIntents and Payment Links carry a non-sensitive Voic payment ID in Stripe metadata for deterministic correlation.

## Consequences

- The platform secret key must remain server-side and be configured for the matching Stripe test or live mode.
- A merchant connection does not need its own webhook endpoint or webhook secret.
- Reconnection and deauthorization can update the provider connection without deleting historical payments or payment events.
- OAuth access-token refresh logic is not part of this integration because API requests use the platform key and `Stripe-Account` header.

## Alternatives considered

- Persisting OAuth access and refresh tokens was rejected because Stripe marks the access-token API flow as deprecated and platform-key authentication is the current recommended path.
- Creating a webhook endpoint per merchant was rejected because Connect webhook endpoints can receive events for all connected accounts and are configured at the platform level.
- Creating products in Voic was rejected because Stripe is the catalog source of truth and its product/price model should not be duplicated locally.
