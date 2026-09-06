# 06: Call orchestration (FAILED payment → Vobiz call → ElevenLabs)

**What to build:** The end-to-end trigger that turns an existing failed-payment flow into a customer voice call and carries context through: extend `CallAttempt` with voice fields, place the Vobiz outbound call on `FAILED` (existing trigger), and attach the ElevenLabs conversation. Plus a demo shortcut so the 3-hour demo does not need a real Stripe failure.

**Blocked by:** 01-contracts, 02-vobiz-ws, 03-elevenlabs-bridge, 04-agent-config, 05-agent-tools (needs all interfaces; start DB + trigger work early, integrate once peers land).

**Status:** ready-for-agent

**Branch:** `feature/voice-06-orchestration`

**Timebox:** 45–60 min. Tests ignored for demo.

**Owns:** `app/models/call_attempt.py` (add 3 nullable cols), `migrations/versions/00xx_voice_mvp.py` (new migration), edits to `app/services/calls/vobiz.py` (extend trigger only), `app/api/voice_demo.py` (new demo trigger, optional but recommended). Must NOT touch `voice_ws.py`, `agent_tools.py`, `bridge.py`, `main.py`, `.env.example`.

## Acceptance criteria

- [ ] Migration adds nullable `elevenlabs_conversation_id`, `customer_phone`, `outcome` to `call_attempts`; `migrate-sql` (offline) generates cleanly.
- [ ] Existing `trigger_recovery_call` still places the Vobiz call on `FAILED` + phone present + one-call-per-payment; now also persists `customer_phone` on the `CallAttempt` and leaves `elevenlabs_conversation_id` for 03 to fill.
- [ ] Demo shortcut exists: `POST /api/v1/voice/demo-trigger {"payment_id": "..."}` (merchant-authenticated) places the same call path without needing a Stripe webhook — this is what the live demo uses.
- [ ] Stored per call: `call_id` (= CallAttempt.id), `payment_id`, `vobiz_call_id` (provider_call_id), `elevenlabs_conversation_id`, `customer_phone`, `outcome`.
- [ ] Manual verify: create FAILED payment with phone → demo-trigger → `CallAttempt` row is `PLACED` with phone stored; `git status` shows only owned files.
