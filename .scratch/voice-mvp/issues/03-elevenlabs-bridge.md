# 03: ElevenLabs voice bridge (Voic ↔ ElevenLabs audio)

**What to build:** The realtime bridge that connects Voic to the ElevenLabs conversational agent: send caller audio to ElevenLabs, receive agent audio, transcode as needed, hand Vobiz-ready bytes back to ticket 02's socket, and persist `elevenlabs_conversation_id` on the `CallAttempt`.

**Blocked by:** 01-contracts (code to the `VoiceBridge` interface and audio formats frozen in `docs/voice-mvp-contracts.md`; do not wait for 02/04/05 code).

**Status:** ready-for-agent

**Branch:** `feature/voice-03-elevenlabs-bridge`

**Timebox:** 60–90 min. Tests ignored for demo.

**Owns:** `app/services/agent/bridge.py` (new, exposes `VoiceBridge` per 01), edits to `app/services/agent/elevenlabs.py` (extend only). Must NOT touch `app/api/voice_ws.py` (02 owns), `app/main.py` (07 owns), `app/models/*`, `migrations/*`.

## Acceptance criteria

- [ ] `VoiceBridge` implements the exact two methods from 01 (`on_vobiz_audio -> bytes | None`, `on_elevenlabs_audio`). 02 can import it with zero changes.
- [ ] Connects to the ElevenLabs agent WebSocket using `ELEVENLABS_API_KEY` + `ELEVENLABS_AGENT_ID` from settings; missing creds → log + return None (never raise into the audio path, so 02's echo fallback keeps working).
- [ ] Transcodes Vobiz format (per 01 assumption, verified in 02's doc) ↔ ElevenLabs 16kHz PCM16 base64 in this module (02 does no transcoding). Use stdlib + `audioop` only (no new binary deps for the demo).
- [ ] On ElevenLabs `conversation_id` receipt, writes `call_attempts.elevenlabs_conversation_id` for the `call_id` (tolerate the column not existing yet — catch the error and log, since 06 owns the migration; do not create your own migration).
- [ ] Manual verify: with fake or real ElevenLabs creds, `on_vobiz_audio(b"...", ...)` returns bytes-or-None without raising; missing creds returns None; `git status` shows only owned files.
