# Voic — AI voice agent that wins back failed payments

> **Razorpay AI Buildathon · Track 03 — AI Revenue Recovery**
> Detect revenue at risk → call the customer → diagnose → recover the money, on one bounded, audited loop.

[![Track](https://img.shields.io/badge/Razorpay%20Buildathon-Track%2003%20·%20AI%20Revenue%20Recovery-0d1117)](https://razorpay.com/buildathon)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20·%20PostgreSQL%20·%20SQLAlchemy%202-009688)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-Next.js%2016%20·%20React%2019%20·%20Tailwind%204-000000)](#tech-stack)
[![Voice](https://img.shields.io/badge/voice-Vobiz%20PSTN%20%E2%86%94%20ElevenLabs%20Conversational%20AI-6d28d9)](#the-recovery-loop)

Every year, Indian merchants lose billions to payments that *almost* worked — a card declined at the last step, a checkout abandoned mid-flow, a renewal mandate that bounced. Today the recovery motion is either silence (hope the customer retries) or spam (10 identical emails).

**Voic closes the loop with a phone call.** When a payment flips to `FAILED`, a recovery agent calls the customer in seconds, speaks like a human (Hinglish, barge-in aware), answers questions about the charge, mints a **fresh Stripe checkout link on the spot**, emails it, and gets out of the way. Every money action is explainable, bounded, and logged — no agent ever invents a URL, and no customer gets called twice for the same failure.

---

## The recovery loop

```text
 Stripe webhook                     Vobiz PSTN call              ElevenLabs
 payment_intent.        ┌───────────────────────────┐        Conversational AI
 payment_failed ──────▶ │  dedupe + guardrails      │ ──▶  agent (Hinglish,
 (verified, signed)     │  CallAttempt claimed       │       barge-in aware)
        │               │  once per payment           │               │
        ▼               └───────────────────────────┘               ▼
 Payment → FAILED          HMAC-signed answer URL        ┌─────────────────────┐
        │                  + media WebSocket              │ agent tools:        │
        ▼                                                        │ · get-payment-status│
 calls enqueue async        8 kHz µ-law  ◀────────────▶  16 kHz PCM│ · create-checkout-  │
 (webhook returns 2xx       bridge, paced playback                 │   link (Stripe)     │
 fast, never blocks)                                               │ · send-email        │
                                                                   └─────────────────────┘
                                                                             │
                                        customer clicks real Stripe checkout ◀┘
                                        payment_intent.succeeded → Payment COMPLETED
                                        open call is closed as RECOVERED
```

One customer journey, end to end: **failure → call → conversation → checkout → money recovered.** Try it yourself with the 10-step runbook in [`docs/voice-demo-runbook.md`](docs/voice-demo-runbook.md).

## What the agent can (and cannot) do

Every action the voice agent takes goes through a token-authenticated tool API (`POST /api/agent/tools/*`, gated by `X-Agent-Token`). The agent's agency is deliberately narrow:

| Tool | What it does | Bounded because |
|---|---|---|
| `get-payment-status` | Reads the failed payment's amount, currency, status, customer contact — same source the greeting is seeded from | Read-only, scoped to the bound payment |
| `create-checkout-link` | Reuses the merchant's own Stripe price to mint a hosted Payment Link | Never manufactures URLs; provider-scoped, price-validated |
| `send-email` | Sends the checkout link via Resend (falls back to a logged `demo: true` response) | Destination defaults to the payment's own customer |

And the hard stopping rules:

- **One call per payment.** Repeat failure webhooks for the same payment never re-call — dedupe is enforced by a persisted `CallAttempt` claim.
- **Success wins.** Any later `COMPLETED` event for the payment closes/cancels the open call job.
- **Phone required.** No verified customer phone on the event → no call, ever.
- **Signed context.** Answer URLs and media sockets are HMAC-bound to `payment_id` + `call_id`; a tampered or replayed URL is rejected before any audio flows.
- **Graceful degradation at every link.** No Vobiz creds → `skipped:vobiz-not-configured`. No ElevenLabs → the telephony layer falls back to a scripted `<Speak>`. The webhook always returns 2xx.

This is the Track 3 bar taken literally: **bounded recovery workflow, stopping rules, and an audit trail** — every call attempt, provider ID, conversation ID, and close timestamp is persisted on `CallAttempt`.

## Architecture

```text
┌────────────────────────── apps/frontend (Next.js 16, App Router) ─────────────────┐
│  merchant signup/login · Stripe OAuth connect · catalog browser · dashboard with  │
│  paginated payments table (sort/filter, live status) · integration health        │
│  (never sees secrets, OAuth tokens, or raw webhook payloads)                     │
└──────────────────────────────────────┬────────────────────────────────────────────┘
                                       │ opaque HTTP-only sessions
┌──────────────────────────────────────▼────────────────── apps/backend (FastAPI) ──┐
│  auth → merchant → merchant-owned resource, resolved on every request             │
│                                                                                   │
│  payments & payment links ── provider abstraction (Stripe adapter, Razorpay-ready)│
│  webhook intake: raw body → signature verify → account-bound merchant resolution  │
│                  → (provider, event_id) dedupe → immutable payment events         │
│  recovery: FAILED transition → CallAttempt claim → Vobiz trigger (async)          │
│  voice: answer XML + /ws/voice/{call_id} bridge → ElevenLabs agent                │
│  agent tools: payment status · checkout link · email (token-gated)                │
│  per-call latency instrumentation: TTFW, queue lag, behind-realtime budget        │
└──────────────────────────────────────┬────────────────────────────────────────────┘
                                       │
                        PostgreSQL + Alembic (11 migrations, idempotent event store)
```

**Engineering decisions that matter** (each documented as an ADR):

- **The signed envelope is the tenant boundary.** Stripe's event `account`/`context` field — not customer email, not metadata, not phone — decides which merchant an event belongs to. Metadata is used only to *correlate* a payment *after* the boundary is resolved. Metadata can never select a merchant. ([ADR-0004](docs/adr/0004-account-less-webhook-correlation.md))
- **Idempotent, order-independent intake.** `(provider, provider_event_id)` uniqueness, immutable verified payloads, no business logic assumes delivery order. Duplicates and out-of-order events are first-class test cases.
- **Credentials never cross to the browser.** Stripe Standard OAuth stores the connected account ID and connection metadata — never deprecated OAuth tokens. Platform secrets are env-only; raw webhook payloads are retained server-side for restricted debugging only ([ADR-0003](docs/adr/0003-raw-webhook-payload-retention.md)).
- **Real-time voice is a budget, not a vibe.** The media bridge is instrumented: time-to-first-word, per-chunk queue lag, and "behind real-time" overruns are measured per call and logged as a latency summary. Playback is a bounded, paced queue with local barge-in (`clearAudio` after 80 ms of caller energy) — so a TTS burst can never deadlock the call.
- **Graceful degradation is designed, not incidental.** If the AI bridge is down, the safe scripted `<Speak>` path still runs. The recovery never gets *worse* because the AI is unavailable.

## Tech stack

| Layer | Choices |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, TanStack Table, Recharts |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL, Alembic |
| Payments | Stripe (Standard OAuth, PaymentIntents, Payment Links, Connect webhooks) behind a provider abstraction |
| Voice | Vobiz (Plivo-compatible) PSTN + bidirectional media WebSocket, 8 kHz µ-law ↔ 16 kHz PCM transcoding (stdlib `audioop` — zero new binary deps) |
| AI | ElevenLabs Conversational AI agent with dynamic variables seeded from the DB and three webhook tools |
| Email | Resend |
| Infra | `make dev` runs both apps; FastAPI `BackgroundTasks` for recovery jobs; 11 Alembic migrations |

## Repository layout

```text
apps/
  frontend/   Next.js merchant dashboard (auth, integrations, payments)
  backend/
    app/
      api/            auth, stripe, payments, webhooks, voice, agent tools
      services/
        providers/    Stripe adapter behind a provider abstraction
        calls/        Vobiz call trigger + guardrails
        agent/        ElevenLabs bridge + per-call latency instrumentation
      models/         merchants, payments, payment events, call attempts
    migrations/       11 Alembic revisions
docs/
  architecture.md            full Phase-1 + voice architecture
  voice-mvp-contracts.md     frozen voice contracts (WS, tools, DB, env)
  voice-vobiz-ws.md          real Vobiz stream protocol notes
  voice-demo-runbook.md      10-step live demo checklist
  adr/                       5 architecture decision records
tests/                       11 API-boundary test suites (pytest)
```

## Quickstart

```bash
git clone https://github.com/Vighnesh-V-H/voic.git && cd voic

make install          # backend venv + frontend npm deps
make migrate          # alembic upgrade head (needs PostgreSQL)
make dev              # FastAPI :8000 + Next.js together
```

Wire your `.env` (see `apps/backend/.env.example`): `DATABASE_URL`, `STRIPE_SECRET_KEY`, `STRIPE_CONNECT_WEBHOOK_SECRET`, plus the voice block (`VOBIZ_*`, `ELEVENLABS_*`, `AGENT_TOOL_TOKEN`, `VOICE_CALLBACK_TOKEN`). Empty voice credentials = voice path logs-and-skips; the rest of the product works without them.

**Verify everything:**

```bash
make verify   # pytest + eslint + next build + offline migration SQL
```

## Running the recovery demo

The full happy path — failed payment → phone rings → agent talks → checkout link lands in the inbox — is a 10-step checklist in [`docs/voice-demo-runbook.md`](docs/voice-demo-runbook.md). Short version:

1. Sign up, connect a Stripe Test Mode account via Standard OAuth.
2. Create a payment; replay `payment_intent.payment_failed` (or use the built-in demo trigger).
3. Vobiz dials the customer; the WebSocket bridge hands audio to the ElevenLabs agent.
4. The agent greets with the payment's real amount and ID, answers questions, and mints a Stripe checkout link on request — emailed before the call ends.
5. Hang up → `CallAttempt` closes with timestamps and the ElevenLabs conversation ID retained.

Every fallback is recorded live-vs-simulated: no telephony creds, no TTS creds, and no email provider each degrade to a documented, tested behavior.

## Test surface

11 pytest suites exercise the API boundary, including the cases graders ask about:

- OAuth state expiry, single-use, and callback handling — no credential leakage
- Webhook signature verification on the raw body; malformed payloads; unknown accounts
- Duplicate-event idempotency and out-of-order persistence
- **Cross-merchant access rejection and "metadata can never select a merchant"**
- Call trigger guardrails: phone required, one call per payment, success closes the call
- WebSocket relay with a simulated Vobiz client against the real bridge

```bash
cd apps/backend && .venv/Scripts/python.exe -m pytest -q        # Windows
cd apps/backend && .venv/bin/python -m pytest -q                # macOS/Linux
```

## Where this goes next

The trigger rule today is `Payment.status → FAILED`. The architecture and allowlist are already designed for the rest of the Track 3 surface, in dependency order:

- **Widen triggers** — `checkout.session.expired` (abandonment) and `invoice.payment_failed` (failed subscription renewals) map to the same `FAILED` transition, so every recovery source stays behind one guarded path.
- **Post-call outcomes** — hangup classification (recovered / promise-to-pay / refused) written back to `CallAttempt.outcome`, closing the attribution loop.
- **Retry sequencers with compliant escalation** — bounded call/email cadences per merchant with quiet hours and per-merchant frequency caps.
- **Measured money recovered** — batch-level recovered-₹ reporting built on the existing payment-event store: recovered vs. control, per intervention.

## Team

Built by Vighnesh V H for the Razorpay AI Buildathon, Track 03 — AI Revenue Recovery. The domain language lives in [`CONTEXT.md`](CONTEXT.md); the decision record in [`docs/adr/`](docs/adr/).
