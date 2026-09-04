# ElevenLabs Agent Setup — Voic Payment Agent (Ticket 04)

Docs-only console setup. Source of truth for routes/header/JSON shapes is
`docs/voice-mvp-contracts.md` (Ticket 01 frozen contracts). This doc copies
those shapes verbatim — if they differ, the contracts doc wins. No code,
no `.env` edits here.

## 1. Agent identity

- Agent name: `Voic Payment Agent`
- Create it in the ElevenLabs dashboard under Agents (conversational AI) → Add agent.
- After creation, copy the agent ID from the agent's settings/URL and paste it as
  `ELEVENLABS_AGENT_ID=` in your local `.env` (copied from `.env.example`).
  The ID itself lives only in `.env` — never commit it.

## 2. First message (uses bound dynamic variables)

Set the agent's first message to (Hinglish, product name + dollar amount —
never the payment ID):

```text
Namaste! Main Voic se bol raha hoon. Aapki {{product_name}} ki {{amount}} dollar ki payment fail ho gayi thi. Kya main payment link dobara aapko bhej doon?
```

`{{product_name}}` and `{{amount}}` are per-call dynamic variables bound by
Voic at call time (product name comes from the Stripe price/product lookup,
falling back to "recent order"); they are not typed in by hand per customer.
`{{payment_id}}` is bound too but exists only for tool calls — never speak it.

## 3. Demo language(s)

Hinglish by default (agent `language: hi`, `hinglish_mode: true`); the agent
switches to plain English or Hindi if the caller prefers. Voic tool APIs are
language-independent.

## 4. Context-passing rule (must follow)

Payment context (`payment_id`, `merchant_id`, `amount`, `currency`,
`customer_phone`, `customer_email`, `product_name`) rides as bound dynamic
variables per call — never LLM-invented. Every tool call re-sends
`payment_id`, and the backend re-verifies it before acting. If a variable is
missing, ask the caller or abort the tool call; never guess an ID, amount, or
phone number.

Bind at call time (per-call overrides when starting the conversation):
`payment_id`, `merchant_id`, `amount`, `currency`, `customer_phone`,
`customer_email`, `product_name`.

### System prompt rules (applied live via API)

- Greet with `{{product_name}}` and `{{amount}}` dollars; NEVER say
  `{{payment_id}}`, merchant id, or any reference number out loud.
- First tool call every conversation: `get_payment_status` with
  `{{payment_id}}`; only offer a checkout link when status is FAILED or
  PENDING; if COMPLETED, congratulate and end.
- Do not read the raw `checkout_url` aloud; offer to email it instead.
- For email: confirm the address (default to `customer_email` from
  `get_payment_status`), then call `send_email`.

## 5. Webhook tool definitions (method POST, copied verbatim from contracts)

Auth for all three tools: header `X-Agent-Token: <AGENT_TOOL_TOKEN>` checked
before any logic. Errors: `{"error": "<CODE>", "message": "..."}` with HTTP
4xx, never 5xx for bad input, never stack traces.

Base URL for all tools is the public backend URL (e.g. ngrok in local dev).
Append the exact paths below.

### 5.1 get-payment-status

```text
POST /api/agent/tools/get-payment-status
  req: {"payment_id": "..."}
  res: {"payment_id": "...", "status": "FAILED", "amount": 1000,
        "currency": "inr", "customer_email": "...", "customer_phone": "..."}
```

- Configure as a webhook tool: method POST, full URL
  `<public-host>/api/agent/tools/get-payment-status`, header
  `X-Agent-Token: <AGENT_TOOL_TOKEN>`, request body `{"payment_id": "..."}`
  (bound from the call's `{{payment_id}}`).
- Call this first in every recovery conversation to confirm the payment is
  still actionable before offering a link or sending email.

### 5.2 create-checkout-link

```text
POST /api/agent/tools/create-checkout-link
  req: {"payment_id": "..."}
  res: {"payment_id": "...", "checkout_url": "https://...", "status": "PENDING"}
```

- Configure as a webhook tool: method POST, full URL
  `<public-host>/api/agent/tools/create-checkout-link`, header
  `X-Agent-Token: <AGENT_TOOL_TOKEN>`, request body `{"payment_id": "..."}`
  (bound from the call's `{{payment_id}}`).
- Reuses the existing Stripe Payment-Link creation for that payment's
  merchant/price (same provider-account scoping as `POST /api/v1/payment-links`);
  never manufacture URLs.

### 5.3 send-email

```text
POST /api/agent/tools/send-email
  req: {"payment_id": "...", "to": "...", "subject": "...", "body": "..."}
  res: {"sent": true, "to": "..."}
```

- Configure as a webhook tool: method POST, full URL
  `<public-host>/api/agent/tools/send-email`, header
  `X-Agent-Token: <AGENT_TOOL_TOKEN>`, request body
  `{"payment_id": "...", "to": "...", "subject": "...", "body": "..."}`.
- Uses existing email infra, or logs + returns `{"sent": true, "to": "..."}`
  with a `demo: true` flag when no provider is configured.

## 6. Transport decision

The implemented path is the WebSocket bridge: Vobiz dials the customer and
streams media to the HMAC-signed `WS /ws/voice/{call_id}` route, while Voic opens the ElevenLabs
agent WebSocket using a short-lived signed URL. `ELEVENLABS_PHONE_NUMBER_ID`
is not required. Configure all three agent tools as **Webhook** tools, not
Client tools; client-tool calls are rejected and logged by the bridge.

## 7. Manual verify

1. A human following sections 1–6 can recreate the agent from scratch.
2. `git status` shows only this one new file: `docs/elevenlabs-agent-setup.md`.
