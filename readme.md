# Voic — AI voice agent that wins back failed payments

> **Razorpay AI Buildathon · Track 03 — AI Revenue Recovery**
> Detect revenue at risk → call the customer → diagnose → recover the money, on one bounded, audited loop.

[![Track](https://img.shields.io/badge/Razorpay%20Buildathon-Track%2003%20·%20AI%20Revenue%20Recovery-0d1117)](https://razorpay.com/buildathon)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20·%20PostgreSQL%20·%20SQLAlchemy%202-009688)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-Next.js%2016%20·%20React%2019%20·%20Tailwind%204-000000)](#tech-stack)
[![Voice](https://img.shields.io/badge/voice-Vobiz%20PSTN%20%E2%86%94%20ElevenLabs%20Conversational%20AI-6d28d9)](#the-recovery-loop)

## The problem: revenue doesn't fail loudly, it leaks quietly

Picture a customer on a Sunday evening. They found the product, they want it, they've entered their card details — and the payment fails. A bank timeout. A daily limit hit. A 3-D Secure OTP that arrived late. The intent was 100% there; the money never moved.

What happens next, today, for almost every merchant in India?

- **Option 1 — silence.** The merchant never even knows. The customer shrugs and buys from a competitor. That revenue is gone, and nobody ever measured it.
- **Option 2 — email blast.** Hours later, a generic "your payment failed, click here" email lands in a spam folder. Click rates are miserable because the customer has no reason to trust a cold email about their own card.
- **Option 3 — a support ticket.** The customer cares enough to reach out, waits a day for a human, and the impulse is long dead.

The uncomfortable truth: **failed payments are usually the highest-intent customers a merchant has.** They picked the product. They were mid-purchase. The only thing missing was a second chance — delivered while that intent is still alive.

And the pattern repeats across the Track 3 surface: checkout abandonment, failed subscription renewals, bounced mandates. Each one is a customer who already said yes and was let down by a payment rail, not by the product.

## How Voic recovers the money

Voic flips the model from *reactive email* to *proactive conversation*. The moment a payment flips to `FAILED`, Voic's AI agent places a real phone call to the customer. Not a robocall — a conversation.

Here's the actual journey, end to end:

1. **Seconds after the failure**, Stripe's verified webhook tells Voic the payment died. Voic records the failure, checks its guardrails (Does this payment have a customer phone? Has it already been called? No? Then this is a valid recovery case), and places a call through telephony.
2. **The customer's phone rings.** They answer. An AI voice greets them — naturally, in Hinglish the way real Indian support calls sound — and already knows *exactly* which charge this is about: "Hi, you tried paying ₹1,499 at 7:42 pm and the payment didn't go through — did you still want the item?"
3. **The agent diagnoses.** The customer might say "my card got blocked", "I didn't recognize this charge", or "I was in a hurry". The agent answers, reassures, and resolves the objection in real time — the thing a dead email can never do.
4. **The agent recovers, right there.** "Want me to send you a fresh payment link?" The agent mints a **brand-new, hosted Stripe checkout link for that exact product and amount** — and emails it while they're still on the call.
5. **The customer pays on their own terms.** They open the link on their phone, see the merchant's real Stripe checkout, and complete the purchase. The success webhook flows back, and Voic marks the case recovered.
6. **The call hangs up.** The conversation ID, timestamps, and outcome are persisted — the audit trail judges can inspect.

Why a *phone call* and not another email? Because voice is the only channel where you can:

- **Reach them in seconds, not hours** — while purchase intent is still warm.
- **Establish trust instantly** — a call that names the exact amount, product, and time is self-authenticating in a way email never is.
- **Handle objections live** — "I didn't authorize this", "my card is blocked", "send me a different link" are conversations, not support tickets.
- **Deliver the fix inside the conversation** — the checkout link arrives *during* the call, converting at the moment of maximum willingness.

That is the thesis: **detect revenue at risk, diagnose it in conversation, and execute the recovery while the customer is still on the phone.**

## What the agent can (and cannot) do

Every action the voice agent takes goes through a token-authenticated tool API (`POST /api/agent/tools/*`, gated by `X-Agent-Token`). The agent's agency is deliberately narrow — this is the Track 3 bar taken literally: **every money action explainable, bounded, and gated.**

| Tool | What it does | Bounded because |
|---|---|---|
| `get-payment-status` | Reads the failed payment's amount, currency, status, customer contact — same source the greeting is seeded from | Read-only, scoped to the bound payment |
| `create-checkout-link` | Reuses the merchant's own Stripe price to mint a hosted Payment Link | Never manufactures URLs; provider-scoped, price-validated |
| `send-email` | Sends the checkout link via Resend (falls back to a logged `demo: true` response) | Destination defaults to the payment's own customer |

And the hard stopping rules — the agent cannot break these no matter what the caller says:

- **One call per payment.** Repeat failure webhooks for the same payment never re-call — dedupe is enforced by a persisted `CallAttempt` claim. A frustrated customer is never ring-spammed by a retrying webhook.
- **Success wins.** Any later `COMPLETED` event for the payment closes/cancels the open call job. The agent never calls someone who already paid.
- **Phone required.** No verified customer phone on the event → no call, ever. The agent can't discover numbers on its own.
- **Signed context.** Answer URLs and media sockets are HMAC-bound to `payment_id` + `call_id`; a tampered or replayed URL is rejected before any audio flows. Nobody can point the calling robot at an arbitrary payment.
- **Graceful degradation at every link.** No Vobiz creds → `skipped:vobiz-not-configured`. No ElevenLabs → the telephony layer falls back to a scripted `<Speak>`. The webhook always returns 2xx — a recovery system must never make the payment path worse.

This is the compliance posture Track 3 asks for: **bounded recovery workflow, stopping rules, and an audit trail.** Every call attempt, provider ID, conversation ID, and close timestamp is persisted on `CallAttempt` — judges can query the trail, not just watch a demo.

## Architecture

Voic is a two-app monorepo with a strict boundary: the browser never touches secrets, the webhook never blocks on calls, and the agent never touches Stripe without going through a gated tool.

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

Read the diagram as four layers, each with one job:

**1. The merchant surface (frontend).** Merchants sign up, connect their existing Stripe account through Standard OAuth (they stay in control — Voic holds no card data and no OAuth tokens), browse their own product catalog, and watch payments land on a live dashboard. When a payment fails, the merchant sees the recovery state, not just an error code. The browser only ever holds an opaque, HTTP-only session cookie — secrets live and die on the server.

**2. The truth layer (webhook intake).** Everything Voic knows about money comes from a single, hardened webhook endpoint. The raw request body is signature-verified *before* parsing; Stripe's signed `account` field — never customer email, never metadata — decides which merchant the event belongs to; and every event is stored immutably with a `(provider, event_id)` uniqueness constraint. Duplicate deliveries and out-of-order events are expected, not exceptional. This layer is deliberately paranoid because everything downstream — the call, the money — trusts it.

**3. The decision layer (recovery trigger).** When an event flips a payment to `FAILED`, a small rules engine decides whether a call is justified: verified failure + phone present + no prior call for this payment. The webhook returns 2xx immediately and the call is enqueued in the background — payment ingestion and recovery are decoupled, so a slow telephony provider can never slow the webhook.

**4. The conversation layer (voice + agent).** A bidirectional media WebSocket bridges the phone network and the AI: customer audio arrives as 8 kHz µ-law from telephony, is transcoded to 16 kHz PCM for ElevenLabs' Conversational AI, and the agent's replies flow back through a bounded, paced playback queue. The agent is seeded with the payment's real context (amount, currency, payment ID) via dynamic variables, and its only superpowers are the three gated tools above. Barge-in is handled locally — 80 ms of caller speech clears the agent's queued audio so the agent never talks over the customer.

**Engineering decisions that matter** (each documented as an ADR):

- **The signed envelope is the tenant boundary.** Metadata is used only to *correlate* a payment *after* the boundary is resolved. Metadata can never select a merchant. ([ADR-0004](docs/adr/0004-account-less-webhook-correlation.md))
- **Idempotent, order-independent intake.** `(provider, provider_event_id)` uniqueness, immutable verified payloads, no business logic assumes delivery order. Duplicates and out-of-order events are first-class test cases.
- **Credentials never cross to the browser.** Stripe Standard OAuth stores the connected account ID and connection metadata — never deprecated OAuth tokens. Platform secrets are env-only; raw webhook payloads are retained server-side for restricted debugging only ([ADR-0003](docs/adr/0003-raw-webhook-payload-retention.md)).
- **Real-time voice is a budget, not a vibe.** The media bridge is instrumented: time-to-first-word, per-chunk queue lag, and "behind real-time" overruns are measured per call and logged as a latency summary. Playback is a bounded, paced queue with local barge-in — so a TTS burst can never deadlock the call.
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
