# 05: Backend agent-tool endpoints (Stripe + email actions)

**What to build:** The three business operations the ElevenLabs agent calls during a call: payment status lookup, Stripe checkout-link creation, and email sending. Simple authenticated JSON APIs per the 01 contract, reusing existing Stripe/email infrastructure.

**Blocked by:** 01-contracts (implement the exact routes/header/JSON from `docs/voice-mvp-contracts.md`; do not wait for 02/03/04).

**Status:** ready-for-agent

**Branch:** `feature/voice-05-agent-tools`

**Timebox:** 60–90 min. Tests ignored for demo.

**Owns:** `app/api/agent_tools.py` (new router), `app/services/agent/tools.py` (new logic). Must NOT touch `app/main.py` (07 wires the router), `app/models/*`, `migrations/*`, voice WS files.

## Acceptance criteria

- [ ] `POST /api/agent/tools/get-payment-status` with `X-Agent-Token` == `AGENT_TOOL_TOKEN` returns `{payment_id, status, amount, currency, customer_email, customer_phone}`; bad token → 401, unknown `payment_id` → 404, all errors as `{"error","message"}`.
- [ ] `POST /api/agent/tools/create-checkout-link` validates `payment_id`, reuses existing Stripe Payment-Link creation for that payment's merchant/price (same provider-account scoping as `POST /api/v1/payment-links`; never manufacture URLs), stores the new link on the payment, returns `{payment_id, checkout_url, status}`.
- [ ] `POST /api/agent/tools/send-email` validates `payment_id` + `to/subject/body`, sends via existing email infrastructure (or logs + returns `{"sent": true}` with a `demo:true` flag if no email provider is configured — document which in code comment), returns `{"sent": true, "to": "..."}`.
- [ ] All three reject missing/invalid `X-Agent-Token` before any business logic; never leak secrets, never return stack traces.
- [ ] Manual verify: with backend running, `curl` each endpoint with right + wrong token and a real `payment_id`; `git status` shows only the two owned files.
