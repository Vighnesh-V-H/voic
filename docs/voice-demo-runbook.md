# Voice MVP — Demo Runbook (Ticket 07)

10-step checklist for the live demo. Goal: failed payment → Vobiz calls the
customer → ElevenLabs talks → customer asks for a checkout link → agent calls
Voic backend → Stripe checkout link created → agent sends it by email.

## Prerequisites

- [ ] PostgreSQL running; `alembic upgrade head` applied (includes
  `0011_voice_mvp_call_fields`).
- [ ] Backend boots: `make backend` (or uvicorn `app.main:app`), `/health` → ok.
- [ ] Public HTTPS base in `VOBIZ_PUBLIC_BASE_URL` + `VOICE_WS_BASE_URL`
  (ngrok in local dev), pointing at this backend.
- [ ] `.env` filled (never commit): `VOBIZ_AUTH_ID`, `VOBIZ_AUTH_TOKEN`,
  `VOBIZ_CALLER_ID`, `VOICE_CALLBACK_TOKEN`, `ELEVENLABS_API_KEY`,
  `ELEVENLABS_AGENT_ID`, `AGENT_TOOL_TOKEN`. `ELEVENLABS_PHONE_NUMBER_ID` is
  not used by the WebSocket bridge.
- [ ] ElevenLabs agent built per `docs/elevenlabs-agent-setup.md`
  (`Voic Payment Agent`, 3 webhook tools pointing at this backend).

## Demo steps

1. **Seed:** merchant signed up, Stripe connected, one product/price, one
   `Payment` in `FAILED` status with a customer phone on its latest
   `payment_event` (or use `VOICE_DEMO_SUCCESS_TRIGGER=true` + a completed
   checkout, where the phone is reliably present).
2. **Trigger (no Stripe replay needed):**
   ```bash
   curl -X POST localhost:8000/api/v1/voice/demo-trigger \
     -H 'Content-Type: application/json' -H "Cookie: <session>" \
     -d '{"payment_id": "<PAYMENT_ID>"}'
   # → {"result": "called:<vobiz_id>", "call_id": "<CALL_ID>", "status": "PLACED"}
   ```
3. **Vobiz places the call** to the customer phone; answer XML / media stream
   opens `wss://<host>/ws/voice/<CALL_ID>`.
4. **WS bridges:** `start` event → `CallAttempt.status = BRIDGED`;
   caller audio flows Voic → ElevenLabs → reply audio flows back.
5. **ElevenLabs talks**, greeting with the bound `{{payment_id}}`/`{{amount}}`.
6. **Customer asks for a payment link** → agent calls
   `POST /api/agent/tools/create-checkout-link` with `X-Agent-Token`.
7. **Verify:** response contains `checkout_url`; check it opens a real Stripe
   checkout page.
8. **Customer asks for email** → agent calls `POST /api/agent/tools/send-email`.
9. **Verify:** `{"sent": true}` (or real inbox if email provider is wired;
   default build logs + returns `demo: true`).
10. **Close:** Vobiz closes the WebSocket on hangup →
    `CallAttempt.status = CLOSED`, `closed_at` set, and
    `elevenlabs_conversation_id` retained. (`outcome` remains empty until a
    post-call outcome handler is implemented.)

## Fallbacks (record live-vs-simulated in the demo notes)

- No Vobiz creds → trigger returns `skipped:vobiz-not-configured`; no call
  attempt is reserved because configuration is checked before persistence.
- No ElevenLabs creds / connection failure → Voic sends Vobiz `stop`; Vobiz
  proceeds to the safe `<Speak>` fallback in the answer XML.
- No email infra → `send-email` returns `{"sent": true, "demo": true}`.

## Contracts

Frozen interfaces: `docs/voice-mvp-contracts.md`. Vobiz audio notes:
`docs/voice-vobiz-ws.md`. Agent setup: `docs/elevenlabs-agent-setup.md`.
