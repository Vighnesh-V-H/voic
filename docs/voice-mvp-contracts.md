# Voice MVP — Frozen Contracts (Ticket 01)

All parallel tickets (02–05) code to this doc verbatim. Do not change these
contracts without updating this file first.

## 1. WebSocket route (Ticket 02 owns)

```text
WS /ws/voice/{call_id}?payment_id={payment_id}&signature={hmac}
```

- `{call_id}` = `CallAttempt.id` (string UUID).
- No auth headers (Vobiz cannot send custom headers). The query signature binds
  `payment_id` + `call_id` using `VOICE_CALLBACK_TOKEN`.
- Invalid/missing signature → 4403; unknown `call_id` → 4404.
- All frames are JSON text per the Vobiz stream protocol (see
  `docs/voice-vobiz-ws.md`): Vobiz sends `start` (with `streamId` +
  `mediaFormat`), then `media` events with base64 audio in
  `media.payload`. We reply with paced `playAudio` frames (base64, chunked
  ~60 ms); checkpoints are kept out of the hot audio path. End of call =
  socket close (no inbound `stop`).
  `CallAttempt` transitions: `start` → `BRIDGED`, close → `CLOSED`.

## 2. Audio formats

- **Vobiz side (requested in answer XML):** 8kHz µ-law mono
  (`contentType="audio/x-mulaw;rate=8000"`), base64 inside `media` events.
  L16 8/16 kHz tolerated if Vobiz sends it.
- **ElevenLabs side:** 16kHz PCM16 mono, base64-encoded on the ElevenLabs
  conversational WebSocket.
- **Transcoding ownership:** Ticket 03 only, stdlib + `audioop`, no new
  binary deps.

## 3. Bridge interface (Ticket 03 implements, 02 imports)

```python
class VoiceBridge:
    async def on_vobiz_audio(self, call_id: str, audio: bytes, format: str) -> bytes | None:
        """Forward caller audio to ElevenLabs; return Vobiz-ready reply bytes or None."""
        ...

    async def on_elevenlabs_audio(self, call_id: str, audio: bytes) -> None:
        """Handle unsolicited ElevenLabs audio (barge-in / events)."""
        ...
```

- 02 wraps bridge initialization in try/except: bridge absent/failing → send a
  Vobiz `stop` event so the safe `<Speak>` fallback executes.
- 03 uses a signed URL for private-agent authentication, sends caller audio as
  `user_audio_chunk`, and receives agent events in a separate continuous task.
- Missing credentials or connection failure is logged and returns control to
  the Vobiz fallback path.
- 03 persists `elevenlabs_conversation_id` on the `CallAttempt` when
  ElevenLabs reports it (tolerate the column missing until 06 lands:
  catch + log, no own migration).
- 03 sends `conversation_initiation_client_data` with `dynamic_variables`
  built from the DB (`call_context(call_id)`: `payment_id`, `merchant_id`,
  `amount` in major units, `currency`, `customer_phone`, plus
  `customer_email` from the latest webhook event for the payment — same
  source `get-payment-status` reads, so prompt and tool agree). Lookup
  failure → `{}` and the agent asks the caller for the payment reference.

## 4. Tool API (Ticket 05 implements, 04 configures the agent)

Auth: header `X-Agent-Token: <AGENT_TOOL_TOKEN>` checked before any logic.
Errors: `{"error": "<CODE>", "message": "..."}` with HTTP 4xx, never 5xx
for bad input, never stack traces.

```text
POST /api/agent/tools/get-payment-status
  req: {"payment_id": "..."}
  res: {"payment_id": "...", "status": "FAILED", "amount": 1000,
        "currency": "inr", "customer_email": "...", "customer_phone": "..."}

POST /api/agent/tools/create-checkout-link
  req: {"payment_id": "..."}
  res: {"payment_id": "...", "checkout_url": "https://...", "status": "PENDING"}

POST /api/agent/tools/send-email
  req: {"payment_id": "...", "to": "...", "subject": "...", "body": "..."}
  res: {"sent": true, "to": "..."}
```

- `create-checkout-link` reuses the existing Stripe Payment-Link creation
  for that payment's merchant/price (same provider-account scoping as
  `POST /api/v1/payment-links`); never manufacture URLs.
- `send-email` uses existing email infra, or logs + returns
  `{"sent": true, "to": "..."}` with a `demo: true` flag when no provider
  is configured.

## 5. DB extension (Ticket 06 owns — nobody else migrates)

`call_attempts` gains three nullable columns:

```text
elevenlabs_conversation_id VARCHAR(255) NULL
customer_phone               VARCHAR(32)  NULL
outcome                      VARCHAR(40)  NULL
```

CallAttempt statuses: `QUEUED → PLACED → BRIDGED → CLOSED`, plus
`FAILED` / `CANCELLED`.

## 6. Env vars (Ticket 07 documents in `.env.example`)

```text
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=
ELEVENLABS_PHONE_NUMBER_ID=
AGENT_TOOL_TOKEN=
VOICE_WS_BASE_URL=
```

Existing `VOBIZ_*` / `VOICE_CALLBACK_TOKEN` unchanged. Empty = path
disabled (log-and-skip); existing webhook + answer XML unaffected.

## 7. Wiring rule (avoids merge conflicts)

- 02/03/05 create NEW modules but do NOT edit `app/main.py`.
- Only 07 edits `app/main.py` (router includes) and `.env.example`.
- Only 06 edits `app/models/call_attempt.py` and `migrations/*`.
- 04 is docs-only.
