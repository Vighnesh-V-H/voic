# Vobiz Audio WebSocket — Real Stream Protocol

Endpoint: `WS /ws/voice/{call_id}?payment_id=...&signature=...` where
`{call_id}` is `CallAttempt.id`. The signature is the same HMAC-bound call
context used by the answer callback; missing or invalid signatures close with
4403. Vobiz connects here because the per-payment answer XML returns:

```xml
<Response>
  <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">
    wss://&lt;host&gt;/ws/voice/{call_id}?payment_id=...&amp;signature=...
  </Stream>
  <Speak>{fallback message}</Speak>
</Response>
```

Source: Vobiz stream-events docs (`/docs/xml/stream/stream-events`).
All frames are JSON text; audio rides as base64 inside `media.payload`.
There is NO binary-frame audio and NO inbound `stop` event.

## Vobiz → Voic

- `start`: `{event:start, start:{callId, streamId, mediaFormat:{encoding, sampleRate}}}`.
  We store `streamId`, fill `provider_call_id` when empty, mark `BRIDGED`.
- `media`: `{event:media, streamId, media:{track:inbound, payload:<b64>}}`,
  ~50/sec, 20 ms frames. Decoded per `start.mediaFormat` (we request
  µ-law 8 kHz; L16 8/16 kHz tolerated), then forwarded without waiting for a
  response. A separate receive task continuously relays ElevenLabs output.
- `playedStream` / `clearedAudio`: delivery acks, logged only.
- End of call = WebSocket close → `CLOSED` + `closed_at`.

## Voic → Vobiz

- `playAudio`: `{event:playAudio, streamId, media:{contentType:audio/x-mulaw,
  sampleRate:8000, payload:<b64>}}`, agent audio chunked ~60 ms (480 B).
- `clearAudio`: sent when ElevenLabs reports an interruption so queued speech
  does not continue over the caller.
- Audio is sent through a bounded, lightly paced queue. Checkpoints are not
  inserted between ElevenLabs audio chunks because those control frames can
  fragment continuous speech; `playedStream` is still tolerated if received.
- Caller energy triggers `clearAudio` locally after 80 ms, without waiting for
  the upstream ElevenLabs interruption event.

## Verification (simulated Vobiz client, real ElevenLabs)

1. Insert a `CallAttempt` row (status `PLACED`), note its `id`.
2. Connect a WS client to `/ws/voice/<id>`, send a `start` event with a
   `streamId` + `mediaFormat {encoding: audio/x-mulaw, sampleRate: 8000}`.
3. Send `media` events (base64 µ-law, 160 B per 20 ms frame).
4. Expect `playAudio` + `checkpoint` replies once the ElevenLabs agent
   speaks (initiation carries `dynamic_variables` from the DB).
5. Close the socket → row becomes `CLOSED`; `elevenlabs_conversation_id`
   persisted when ElevenLabs reports it.
