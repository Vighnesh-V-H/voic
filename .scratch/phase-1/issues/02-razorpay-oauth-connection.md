# 02: Connect a merchant's Razorpay account through OAuth

**What to build:** An authenticated merchant can start Razorpay authorization, complete the callback, and see Razorpay connected in Voic without any OAuth credentials being exposed.

**Blocked by:** #1: Bootstrap Voic and create an authenticated merchant (closed)

**Status:** ready-for-agent

- [ ] An authenticated merchant can initiate Razorpay OAuth.
- [ ] The backend generates a cryptographically random state and stores it server-side with the initiating merchant.
- [ ] The callback rejects missing, invalid, reused, or mismatched state before exchanging the authorization code.
- [ ] The authorization code is exchanged server-side through a provider abstraction.
- [ ] The Razorpay account ID, scopes, access-token expiry, and encrypted access/refresh tokens are persisted in a provider connection.
- [ ] OAuth failures return safe, user-facing error states without leaking provider details or credentials.
- [ ] The frontend shows connected/disconnected status without returning tokens or secrets.
- [ ] The merchant cannot initiate or view another merchant's provider connection.
- [ ] Tests cover state generation, state rejection, successful exchange, encrypted storage, safe responses, and tenant isolation.
- [ ] Refresh-token handling and rotation are covered in this ticket.
- [ ] Webhook creation and payment-event ingestion are outside this ticket.
