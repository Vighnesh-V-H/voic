# ADR-0001: Server-Validated HTTP-Only Sessions

## Status

Accepted

## Context

Voic needs authenticated frontend requests while keeping authentication credentials out of browser-managed storage. The backend must also retain authority over whether a session is valid and which merchant a user can access.

## Decision

Voic uses opaque, randomly generated session tokens in HTTP-only cookies. The backend stores only a hash of each token, validates the hash and expiry on every protected request, and resolves the session to a user and merchant. The cookie is configured with `SameSite=Lax`, and secure cookies are enabled through environment configuration for deployed environments.

## Consequences

- Browser JavaScript cannot read the session token.
- Session revocation and expiry remain backend-controlled.
- The application needs persistent session storage and cleanup over time.
- The frontend proxy can only use cookie presence as an early navigation hint; the backend remains the authentication authority.

## Alternatives considered

- JWTs stored in browser storage were rejected because they increase exposure to client-side script compromise and make revocation less direct.
- A token in a normal cookie was rejected because JavaScript could read it.
