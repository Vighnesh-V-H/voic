# 01: Bootstrap Voic and create an authenticated merchant

**What to build:** A developer can run the Voic frontend, backend, and PostgreSQL-backed persistence, create a merchant account, log in, and access a protected merchant-scoped request.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The Next.js application runs.
- [ ] The FastAPI backend runs.
- [ ] PostgreSQL is configured for local development.
- [ ] Database migrations can create the required user and merchant persistence.
- [ ] Signup creates a user and exactly one associated merchant.
- [ ] Passwords are stored only as secure hashes.
- [ ] Login succeeds with valid credentials and fails with invalid credentials.
- [ ] Protected requests resolve the authenticated user to their merchant.
- [ ] A merchant cannot access another merchant's resources.
- [ ] Automated tests cover signup, login, invalid credentials, and merchant association.
- [ ] Secrets are supplied through environment configuration, with an `.env.example` containing variable names only.
- [ ] Voice, recovery, Razorpay, webhooks, and payment events are explicitly outside this ticket.
