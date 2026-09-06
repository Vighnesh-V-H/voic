# 04: ElevenLabs agent configuration + tool definitions (console work, zero code)

**What to build:** The `Voic Payment Agent` in the ElevenLabs dashboard, configured to use Voic's three tool endpoints with payment/call context. This ticket writes docs only — no backend code — so it has zero merge conflicts and can run fully parallel.

**Blocked by:** 01-contracts (point the agent's tools at the exact routes/header/JSON frozen in `docs/voice-mvp-contracts.md`; do not wait for 05 to implement them).

**Status:** ready-for-agent

**Branch:** `feature/voice-04-agent-config`

**Timebox:** 45–60 min. Needs ElevenLabs dashboard access + the three secrets.

**Owns:** `docs/elevenlabs-agent-setup.md` (new). Must NOT touch any `app/*`, `migrations/*`, `.env*` files.

## Acceptance criteria

- [ ] `docs/elevenlabs-agent-setup.md` records: `ELEVENLABS_AGENT_ID`, agent name `Voic Payment Agent`, first message (greets with `{{payment_id}}` / `{{amount}}` dynamic variables), language(s) for demo, and the three webhook tool definitions with EXACT URLs (`/api/agent/tools/get-payment-status`, `/create-checkout-link`, `/send-email`), method POST, header `X-Agent-Token: <AGENT_TOOL_TOKEN>`, and JSON request/response shapes copied from 01.
- [ ] Doc states the context-passing rule: payment context (`payment_id`, `merchant_id`, `amount`, `currency`, `customer_phone`) rides as bound dynamic variables per call, never LLM-invented; tool calls re-send `payment_id` and the backend re-verifies it.
- [ ] Doc lists the SIP-trunk number assignment IF using the fast SIP path (`ELEVENLABS_PHONE_NUMBER_ID` ← Vobiz DID imported as SIP trunk, agent assigned to it), or marks WS-bridge as the demo path — one line decision, no implementation.
- [ ] Manual verify: a human can follow the doc to recreate the agent; `git status` shows only the one doc file.
