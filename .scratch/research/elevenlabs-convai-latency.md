# Research: ElevenLabs ConvAI latency settings and telephony-native audio formats

Ticket: Vighnesh-V-H/voic#34 (parent map: #33). Researched 2026-09-06 against
ElevenLabs docs (elevenlabs.io/docs, "ElevenAgents" platform docs) and the
official AsyncAPI websocket spec. No app code changed.

Context: our bridge is Vobiz media WS (8 kHz µ-law, 20 ms frames) ↔
FastAPI bridge (`apps/backend/app/api/voice_ws.py`,
`apps/backend/app/services/agent/bridge.py`) ↔ ConvAI WS
(`wss://api.elevenlabs.io/v1/convai/conversation`, currently pcm_16000),
with µ-law 8k ↔ PCM16 16k transcoding in the bridge
(`docs/voice-vobiz-ws.md`, `docs/voice-mvp-contracts.md`).

## 1. Agent configuration affecting time-to-first-word

All fields live in `conversation_config` of the agent (dashboard / Agents API).
Primary source: ElevenLabs official agent-configuration reference
(https://github.com/elevenlabs/skills/blob/main/agents/references/agent-configuration.md)
and https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow.

- **Turn eagerness** — `conversation_config.turn.turn_eagerness`:
  `eager` | `normal` | `patient` (default `normal`). `eager` makes the agent
  jump in at the earliest opportunity; docs recommend it for fast-paced /
  customer-service use cases. Also documented at
  https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow.
- **Turn timeout** — `turn.turn_timeout` (seconds to wait before re-engaging
  the user; default 7, range 1–30 in the conversation-flow doc). Shorter =
  more responsive re-prompting after silence.
- **Turn detection model** — `turn.turn_model`: `turn_v3` (default) or
  `turn_v2`; plus `turn.speculative_turn` (bool, default false) for
  speculative turn detection. This is ElevenLabs' proprietary turn-taking
  model (see https://elevenlabs.io/docs/eleven-agents/overview).
- **Silence sensitivity / VAD** — there is a `vad` block in
  `conversation_config` (Voice Activity Detection config); the server also
  emits `vad_score` events (0–1 probability the user is speaking). No single
  documented "silence sensitivity ms" knob; the effective knobs are
  `turn_eagerness`, `turn_timeout`, and `silence_end_call_timeout`.
- **Soft timeout fillers** — `turn.soft_timeout_config`
  (`timeout_seconds` default -1 disabled, range 0.5–8 s, recommended 3.0;
  static/LLM-generated filler like "Hhmmmm...yeah."). Mitigates perceived
  latency while the LLM thinks; triggers once per turn
  (https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow).
- **TTS model** — `tts.model_id`. Latency table from the agent-config
  reference: `eleven_flash_v2_5` ~75 ms model inference (32 langs,
  recommended for low latency), `eleven_flash_v2` ~75 ms (EN),
  `eleven_turbo_v2_5` / `eleven_turbo_v2` ~250–300 ms,
  `eleven_multilingual_v2` / `eleven_v3_conversational` standard (slowest).
  Per-call override of `tts.model_id` exists in
  `conversation_initiation_client_data.conversation_config_override.tts.model_id`
  (enum includes all of the above) per the ConvAI websocket AsyncAPI spec
  (https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket).
- **Response speed multiplier** — `tts.speed`, range 0.7–1.2 (default 1.0).
  Also per-call overridable via `conversation_config_override.tts.speed`.
  Overridable only if the agent's Security → overrides allow it
  (https://elevenlabs.io/docs/eleven-agents/customization/personalization/overrides).
- **LLM choice** — `agent.prompt.llm` + `temperature` + `max_tokens`. Fast
  options include `gemini-2.0-flash`/`gemini-2.5-flash` family and
  ElevenLabs-hosted `gpt-oss-120b` ("ultra-low latency"). Low-latency
  reference config uses `gemini-2.0-flash`, `temperature 0.3`,
  `max_tokens 100`, `turn_eagerness: eager`, `turn_timeout: 3`
  (agent-configuration reference). `enable_reasoning_summary` should stay
  off for lower time-to-first-byte. Custom LLMs supported via
  `agent.prompt.custom_llm`.
- **First message** — `agent.first_message` (agent speaks immediately at
  conversation start); `agent.disable_first_message_interruptions` (bool,
  default false) prevents the caller barging in over the greeting. Both
  overridable per call (`conversation_config_override.agent.first_message`)
  subject to Security overrides being enabled.
- **Legacy TTS streaming-latency tier** — `optimize_streaming_latency`
  (`0`–`4`) still appears in the websocket override schema only as a
  per-voice attribute (`tts.supported_voices[].optimize_streaming_latency`);
  there is no documented agent-level "latency optimization tier" setting.
  The documented levers are model choice, LLM choice, and speed.

## 2. ConvAI websocket protocol facts

Sources: https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets,
https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket
(AsyncAPI spec),
https://elevenlabs.io/docs/eleven-agents/customization/events/client-events,
https://elevenlabs.io/docs/eleven-agents/customization/events/client-to-server-events.

- **Handshake**: connect to
  `wss://api.elevenlabs.io/v1/convai/conversation?agent_id=...` (public
  agents) or a signed URL from
  `GET /v1/convai/conversation/get-signed-url` (private agents). First
  client message is `conversation_initiation_client_data` (may be the bare
  `{"type": "conversation_initiation_client_data"}`); the server then sends
  `conversation_initiation_metadata` carrying the negotiated
  `agent_output_audio_format` and `user_input_audio_format`.
- **Audio in**: client sends `{"user_audio_chunk": "<base64>"}` messages.
  No acknowledgement; chunk cadence is ours to choose ("Optimized Chunking:
  tweak the audio chunk duration to balance latency and efficiency" —
  web-sockets page). Docs recommend jitter buffers and adaptive buffering.
- **Audio out**: server sends `audio` events
  (`{type:"audio", audio_event:{audio_base_64, event_id, alignment, is_final}}`).
  Chunk/burst sizes are NOT officially documented; the docs only say audio
  arrives "in chunks" and that clients must implement queuing "to prevent
  overlapping" playback. `is_final: true` marks the last chunk of the
  current agent response; `alignment` gives character-level timings
  (useful for precise playback pacing).
- **Per-call overrides** — `conversation_initiation_client_data` supports:
  `conversation_config_override` (agent: `first_message`, `language`,
  `prompt.{prompt,llm,tool_ids,knowledge_base}`; tts: `model_id`,
  `voice_id`, `stability`, `speed`, `similarity_boost`,
  `pronunciation_dictionary_locators`; conversation: `text_only`,
  `max_duration_seconds`; asr: `keywords`; turn: `soft_timeout_config`),
  plus `dynamic_variables`, `custom_llm_extra_body`, `user_id`,
  `source_info.source` (e.g. `twilio`, `sip_trunk`), `branch_id`,
  `environment`, `starting_workflow_node_id`, `procedure_ids`.
  IMPORTANT: the override schema does NOT include audio formats —
  `user_input_audio_format` / `agent_output_audio_format` are agent-level
  config only (see §3). Overrides are gated by the agent's Security
  settings; supplying a non-enabled override errors (soft-disallow for
  asr.keywords) (https://elevenlabs.io/docs/eleven-agents/customization/personalization/overrides).
- **Barge-in semantics**: the server detects user speech during agent
  playback and emits an `interruption` event
  (`{type:"interruption", interruption_event:{event_id}}`; the JS
  voice-stream example also shows an optional `reason` field) followed by
  `agent_response_correction` containing the truncated text of what the
  agent had said. The client is expected to stop/flush queued agent audio
  when it receives `interruption`. Interruptions can be disabled in agent
  config (Conversation flow → Interruptions), with
  `transcribe_on_disabled_interruptions` to still capture user speech, and
  `interruption_ignore_terms` to ignore backchannels
  (conversation-flow + client-events pages). Our bridge currently does local
  caller-energy detection + `clearAudio` after 80 ms without waiting for the
  upstream `interruption` event — that remains valid and faster than
  round-tripping through ElevenLabs.
- **Ping/keepalive**: the server sends
  `{type:"ping", ping_event:{event_id, ping_ms?}}` and the client MUST
  respond `{"type":"pong", "event_id": <ping_event.event_id>}`. The official
  example delays the pong by `ping_ms`, but a prompt pong keeps the
  connection alive; failure to pong breaks the session. Client can also
  send `{"type":"user_activity"}` to reset turn-timeout timers during
  silence, and `contextual_update` / `user_message` for non-audio input.
- **Latency measurement**: the Python SDK exposes
  `callback_latency_measurement` (per-response latency in ms) — useful for
  instrumenting our bridge's time-to-first-word.

## 3. Telephony-native audio formats (can we skip transcoding?)

**Yes — µ-law 8 kHz is natively supported on both directions of the ConvAI
websocket.** Sources: the ConvAI websocket AsyncAPI spec
(https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket)
and the "Register Twilio calls" guide
(https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/register-call).

- The `conversation_initiation_metadata` schema enumerates, for BOTH
  `agent_output_audio_format` and `user_input_audio_format`:
  `pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_44100`,
  `pcm_48000`, **`ulaw_8000`**.
- Agent config fields: `conversation_config.asr.user_input_audio_format`
  (e.g. `ulaw_8000`) and `conversation_config.tts.agent_output_audio_format`
  (dashboard: Voice section → "μ-law 8000 Hz" output; Advanced → "μ-law
  8000 Hz" input — exactly the Twilio register-call setup).
- These are **agent-level** settings; they cannot be overridden per call
  from `conversation_initiation_client_data` (§2). So the spec decision is:
  set the agent to `ulaw_8000` in/out once, and the bridge can forward Vobiz
  base64 µ-law frames to ConvAI as `user_audio_chunk` and relay ConvAI
  `audio` events straight to `playAudio` — **zero transcoding**, removing
  the µ-law↔PCM16 resample/encode work (audioop) from the hot path.
- Caveats: our `docs/voice-mvp-contracts.md` froze "ElevenLabs side: 16 kHz
  PCM16" — that contract would need a revision if we adopt `ulaw_8000`.
  Also confirm quality: ASR at 8 kHz µ-law is what every Twilio/Plivo-style
  integration runs on, but it is a quality/accuracy tradeoff vs 16 kHz PCM.
  Note the negotiated format is echoed in
  `conversation_initiation_metadata`, so the bridge can assert it at
  connect time.

## 4. ElevenLabs published guidance on streaming performance

Source: https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization
and https://elevenlabs.io/docs/eleven-api/concepts/latency.

- **Four latency principles**: use Flash models (~75 ms model inference);
  leverage streaming; consider geographic proximity; choose appropriate
  voices. Voice ordering fastest→slowest: default/premade, synthetic, IVC,
  then PVC (PVC can add latency).
- **Streaming vs HTTP**: regular HTTP endpoint returns the whole file
  (worst for latency); streaming endpoints progressively return chunks
  (best when text is known up-front); **websockets are bidirectional** and
  recommended for real-time/LLM-driven text. For ConvAI the whole
  ASR→LLM→TTS loop is already on one websocket, so this is satisfied.
- **Chunking**: on TTS websockets, `auto_mode` handles generation triggers;
  with a manual chunk schedule, too-small text stalls generation
  ("if only 50 of 125 scheduled characters arrive, the model stalls").
  Analogue for ConvAI: don't drip feed tiny prompt/tool inputs; our
  ~60 ms `playAudio` chunking is a client-side choice, not upstream.
- **Geography**: TTFB for Flash over websockets is 100–150 ms from
  NA/EU/SE-Asia and **150–200 ms from South Asia** (our callers are INR
  payments, so India-region RTT matters). Regional websocket endpoints
  exist per the AsyncAPI spec: `api.us.elevenlabs.io`,
  `api.eu.residency.elevenlabs.io`, `api.in.residency.elevenlabs.io`,
  `api.sg.residency.elevenlabs.io` (residency endpoints are part of the
  data-residency offering). `x-region` response header reveals serving
  region. Enterprise gets increased concurrency + priority rendering queue.

## Decision-relevant summary

1. Biggest bridge-side win: switch agent to `ulaw_8000` in/out and delete
   all transcoding; assert format from `conversation_initiation_metadata`.
   Contract doc `voice-mvp-contracts.md` §2 must be revised first.
2. Biggest agent-side wins for time-to-first-word: `eleven_flash_v2_5`,
   fast LLM (`gemini-2.0-flash`-class or `gpt-oss-120b`), low
   `max_tokens`, `turn_eagerness: eager`, brief `first_message`, and
   `optimize_streaming_latency`-free config (no such global tier).
3. Per-call overrides (first_message, TTS model/speed/voice, prompt,
   dynamic_variables) are possible via `conversation_initiation_client_data`
   but audio formats are NOT per-call — they are agent-level only.
4. Keep our local 80 ms caller-energy `clearAudio`: ElevenLabs barge-in
   events (`interruption` + `agent_response_correction`) arrive from the
   server side and are strictly slower than local detection; still handle
   both, and always pong `ping` events.
5. Consider region: `api.in.residency.elevenlabs.io` / `api.us...` are
   available as websocket base URLs; South-Asia TTFB is 150–200 ms vs
   100–150 ms elsewhere.

## Source URLs

- Agent configuration reference: https://github.com/elevenlabs/skills/blob/main/agents/references/agent-configuration.md
- Conversation flow (turn eagerness, timeouts, soft timeout, interruptions): https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow
- Overrides (per-call security-gated overrides): https://elevenlabs.io/docs/eleven-agents/customization/personalization/overrides
- ConvAI WebSocket guide: https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets
- ConvAI WebSocket AsyncAPI reference (formats, events, overrides schema, regional endpoints): https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket
- Client events (ping/pong, audio, interruption correction, vad_score): https://elevenlabs.io/docs/eleven-agents/customization/events/client-events
- Client-to-server events (user_activity, contextual_update): https://elevenlabs.io/docs/eleven-agents/customization/events/client-to-server-events
- Register Twilio calls (μ-law 8000 Hz in/out setup): https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/register-call
- Latency optimization guide: https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization
- Understanding latency: https://elevenlabs.io/docs/eleven-api/concepts/latency
- ElevenAgents overview (turn-taking model): https://elevenlabs.io/docs/eleven-agents/overview
