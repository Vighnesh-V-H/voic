# 01: Freeze voice-MVP contracts (unblocks all parallel work)

**What to build:** A single frozen contract doc that every other ticket codes against, so Agents 2–5 never block on each other's code. This is the only ticket that must finish first (~15 min). After this, tickets 02–05 run fully parallel.

**Blocked by:** None (can start immediately). All other tickets are blocked by this one.

**Status:** ready-for-agent

**Branch:** `feature/voice-01-contracts`

**Timebox:** 15 min. Do not build audio, tools, or orchestration here — only write the contract file.

**Owns (no other ticket touches these):** `docs/voice-mvp-contracts.md` (new file, the deliverable).

**Must NOT touch:** `app/main.py`, `app/api/*`, `app/services/*`, `app/models/*`, `migrations/*`, `.env.example` (07 owns those).

## Acceptance criteria

- [ ] `docs/voice-mvp-contracts.md` exists and freezes all of the following (copy exact values, agents code to them verbatim):
- [ ] **WS route:** `WS /ws/voice/{call_id}` where `{call_id}` = `CallAttempt.id` (string UUID). No auth headers (Vobiz cannot send custom headers). On connect, look up `CallAttempt` by id; unknown id → close with code 4404. Control messages are JSON text frames: `{"event":"start","call_id":"..."}` and `{"event":"stop","call_id":"..."}`. Audio frames are binary. Document this exact shape.
- [ ] **Audio assumption (02 verifies, 03 codes to it):** Vobiz side = 8kHz µ-law mono (verify against real Vobiz docs/traffic in 02; if different, 02 updates only `docs/voice-vobiz-ws.md`, contract stays). ElevenLabs side = 16kHz PCM16 mono base64. Bridge (03) owns all resampling/transcoding; 02 just relays raw bytes plus a `format` label and never transcodes.
- [ ] **Bridge interface (03 implements, 02 consumes):** Python interface `VoiceBridge` with `async def on_vobiz_audio(call_id: str, audio: bytes, format: str) -> bytes | None` (returns ElevenLabs reply audio in Vobiz format, or None) and `async def on_elevenlabs_audio(call_id: str, audio: bytes) -> None`. 02 imports it but wraps the import in try/except so 02 works standalone when 03 is not merged yet (fallback: echo audio back).
- [ ] **Tool API (05 implements, 04 configures agent to call):** exact routes, header, request/response JSON:
  ```text
  POST /api/agent/tools/get-payment-status   header X-Agent-Token: <AGENT_TOOL_TOKEN>
    req: {"payment_id": "..."}  res: {"payment_id": "...", "status": "FAILED", "amount": 1000, "currency": "inr", "customer_email": "...", "customer_phone": "..."}
  POST /api/agent/tools/create-checkout-link header X-Agent-Token: <AGENT_TOOL_TOKEN>
    req: {"payment_id": "..."}  res: {"payment_id": "...", "checkout_url": "https://...", "status": "PENDING"}
  POST /api/agent/tools/send-email           header X-Agent-Token: <AGENT_TOOL_TOKEN>
    req: {"payment_id": "...", "to": "...", "subject": "...", "body": "..."}  res: {"sent": true, "to": "..."}
  ```
  Errors are always `{"error": "<CODE>", "message": "..."}` with HTTP 4xx (never 5xx for bad input, never stack traces).
- [ ] **DB extension (06 implements, nobody else migrates):** `call_attempts` gains nullable `elevenlabs_conversation_id VARCHAR(255)`, `customer_phone VARCHAR(32)`, `outcome VARCHAR(40)`. Statuses used: `QUEUED → PLACED → BRIDGED → CLOSED`, plus `FAILED`/`CANCELLED`. Only ticket 06 may create/edit the migration or `app/models/call_attempt.py`.
- [ ] **Env vars (07 wires into `.env.example`, everyone reads):** `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID`, `AGENT_TOOL_TOKEN`, `VOICE_WS_BASE_URL` (public wss base, e.g. ngrok https→wss), existing `VOBIZ_*`/`VOICE_CALLBACK_TOKEN` unchanged.
- [ ] **Wiring rule (avoids merge conflicts):** tickets 02/03/05 create NEW router/service modules but do NOT edit `app/main.py`. Ticket 07 is the only ticket that edits `app/main.py` (router includes) and `.env.example`.
- [ ] Manual verify: `docs/voice-mvp-contracts.md` readable; no code changes (`git status` shows only that one new file).
