# ADR-0005: Bridge Vobiz Media to an ElevenLabs Voice Agent

## Status

Accepted

## Context

The static Vobiz Speak flow (`app/api/voice.py`) plays a one-way reminder and
hangs up: the customer cannot ask questions, request a new payment link, or
confirm payment. Failed-payment recovery needs a real conversation
(English + Hindi) that can answer status questions, create checkout links,
and send emails, without ever giving the agent direct access to Stripe
credentials or cross-merchant data.

## Decision

1. Telephony stays on Vobiz. Voic places the recovery call through the Vobiz
   Call API; the answer XML opens an HMAC-signed bidirectional media WebSocket
   to Voic.
2. Voic opens a short-lived signed ElevenLabs agent WebSocket, sends payment
   context (`payment_id`, `merchant_id`, `amount`, `currency`,
   `customer_phone`) as bound dynamic variables, and relays audio concurrently
   in both directions. Payment IDs are never LLM-invented; the backend verifies
   the merchant-owned payment before dialing and on every tool call.
3. The agent performs business operations only through Voic tool APIs
   (`POST /api/agent/tools/*`), authenticated with `AGENT_TOOL_TOKEN` and
   scoped to the signed call context. Stripe/API credentials remain
   exclusively in the Voic backend.
4. Outcomes return through the ElevenLabs post-call transcription webhook
   (HMAC-verified) mapped to the CallAttempt by conversation ID, alongside
   the existing Vobiz hangup handling. The conversation ID is persisted on
   the CallAttempt.
5. Missing ElevenLabs configuration disables the agent path with a logged
   skip; webhooks and the static Vobiz flow keep working.

## Consequences

- New required console setup (Vobiz media streaming + ElevenLabs agent) is
  documented in the backend README; all backend secrets stay in `.env` with
  safe empty defaults per the #18 contract.
- The bridge requests short-lived signed URLs server-side; the ElevenLabs API
  key is never placed in the Vobiz stream URL.
- Per-call cost moves from one Vobiz TTS playback to an ElevenLabs
  conversation; one-call-per-payment dedupe still bounds spend.
- Bilingual prompts (English + Hindi) are agent configuration, versioned
  alongside tool definitions, not backend code.
