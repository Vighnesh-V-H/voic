# 02: Vobiz audio WebSocket endpoint (relay only, no transcoding)

**What to build:** A working bidirectional Vobiz audio socket: Vobiz connects, Voic receives caller audio and sends audio back, and call start/stop is tracked on the `CallAttempt`. Transcoding and ElevenLabs are NOT this ticket — relay raw bytes and hand them to the bridge hook from 01.

**Blocked by:** 01-contracts (read `docs/voice-mvp-contracts.md` first; you may start from the draft in 01 while it is being frozen, but match its final WS path/message shapes exactly).

**Status:** ready-for-agent

**Branch:** `feature/voice-02-vobiz-ws`

**Timebox:** 60–90 min. Tests ignored for demo (do not write/update tests).

**Owns:** `app/api/voice_ws.py` (new), `docs/voice-vobiz-ws.md` (new). Must NOT touch `app/main.py` (07 wires it), `app/models/*`, `migrations/*`, tool files.

## Acceptance criteria

- [ ] `WS /ws/voice/{call_id}` accepts connections; unknown `call_id` closes with code 4404.
- [ ] Binary frames from Vobiz are received; binary frames can be sent back (prove with echo fallback: when bridge module from 03 is absent, echo received bytes back so the path is demoable standalone).
- [ ] JSON text frames `{"event":"start"...}` / `{"event":"stop"...}` update `CallAttempt.status` (`PLACED → BRIDGED` on start, `→ CLOSED` with `closed_at` on stop/disconnect). Import of the 03 bridge is wrapped in try/except (works with or without 03 merged).
- [ ] `docs/voice-vobiz-ws.md` documents the EXACT observed Vobiz audio format and message structure (codec, sample rate, channels, frame size, who sends `start`/`stop`, answer-XML `<Stream>` URL used). If reality differs from the 01 assumption (8kHz µ-law), record the truth here without changing 01.
- [ ] Existing static `GET/POST /api/v1/voice/answer` XML flow still works (do not modify `app/api/voice.py` except if needed for `<Stream>` URL — prefer leaving it untouched).
- [ ] Manual verify: run backend (`make backend` or uvicorn), connect with a WS client to `/ws/voice/<real-call-attempt-id>`, send binary frame, get echo back; `git status` shows only the two owned files.
