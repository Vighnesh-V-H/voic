# Voic backend

The backend is a FastAPI application backed by PostgreSQL. From this directory:

```text
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and update the database connection before starting the server. The API is versioned under `/api/v1`.

The default local PostgreSQL database is `voic` with user `voic` and password `voic`. A PostgreSQL installation or development environment must provide that database; the application does not silently fall back to SQLite.

## Stripe webhooks

Configure one Stripe Connect webhook for the platform endpoint:

```text
https://<public-host>/api/v1/webhooks/stripe
```

Enable events from connected accounts and select the payment event families
needed by the merchant, including `payment_intent.succeeded`,
`payment_intent.payment_failed`, `checkout.session.completed`,
`checkout.session.async_payment_failed`, `charge.succeeded`, and
`charge.failed`. Set the endpoint signing secret as
`STRIPE_CONNECT_WEBHOOK_SECRET`. The handler stores every event delivered for a
known connected account, including events for Stripe products that were not
created by Voic.

For local Connect forwarding, use the Connect flag so Stripe preserves the
connected-account envelope:

```text
stripe listen --forward-connect-to localhost:8000/api/v1/webhooks/stripe
```

If local account-level forwarding omits `account`/`context`, set
`STRIPE_WEBHOOK_ACCOUNT_ID` to the connected `acct_...` ID, or rely on the
single-account development fallback. The fallback is rejected when multiple
connected accounts could match; metadata is never used to choose a merchant.

## Voice recovery calls (Vobiz)

Failed payments trigger one outbound recovery call through Vobiz. Setup path:

```text
1. Sign up at https://console.vobiz.ai and copy the Auth ID + Auth Token
2. Buy a voice-enabled DID number (the caller ID shown to customers)
3. Expose this backend on a public HTTPS URL (ngrok in local dev)
4. Copy `.env.example` to `.env` and fill the VOBIZ_* / VOICE_* values
```

Relevant settings (`VOBIZ_AUTH_ID`, `VOBIZ_AUTH_TOKEN`, `VOBIZ_CALLER_ID`,
`VOBIZ_PUBLIC_BASE_URL`, `VOICE_CALLBACK_TOKEN`) are documented in
`.env.example` and left empty by default. Empty means calling is disabled:
webhooks keep working and the trigger logs and skips. Recovery calls use the
per-payment `/api/v1/voice/answer` URL; the legacy static answer URL setting is
not used for recovery calls.

Callback authentication: Vobiz posts cannot carry custom headers, so every
per-call answer/hangup URL carries a signature over its payment and call
context. `VOICE_CALLBACK_TOKEN` is the long random signing key generated once
per deployment; the secret itself is never sent to Vobiz or exposed in a URL.

## Conversational voice agent (Vobiz + ElevenLabs WebSockets)

Vobiz places the phone call and opens the signed media stream served by this
backend. Voic then opens a private ElevenLabs conversational WebSocket, relays
caller and agent audio concurrently, and executes agent webhook tools. If the
ElevenLabs connection fails, Voic stops the stream and Vobiz plays the safe
`<Speak>` fallback from the answer XML.

Setup path:

```text
1. Expose the backend through public HTTPS/WSS and set VOBIZ_PUBLIC_BASE_URL
   plus VOICE_WS_BASE_URL to that origin.
2. Create the ElevenLabs recovery agent. Its first message uses
   {{payment_id}} / {{amount}} and its three tools are Webhook tools pointing
   to /api/agent/tools/* with the X-Agent-Token header.
3. Set ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, and AGENT_TOOL_TOKEN in .env.
4. Place a Vobiz recovery call; the answer XML connects Vobiz media to
   /ws/voice/{call_id} with an HMAC-signed query string.
```

`ELEVENLABS_PHONE_NUMBER_ID` is only needed for an alternative direct-SIP
integration; this WebSocket bridge does not use it. Empty WebSocket credentials
disable the conversational path without breaking payment webhooks or the safe
voice fallback.
