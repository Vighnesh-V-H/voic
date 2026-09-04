# Voice Agent — When To Call (High-Level Guideline)

Own voice agent. The webhook decides. Call only when a payment transitions to `FAILED`.

Insertion point: `apps/backend/app/api/webhooks.py:stripe_webhook`, after the `Payment.status = FAILED` commit. Enqueue a call job async — never block the webhook, never call before commit.

Implemented (v1): the webhook sets a `failed_transition` flag when the event
flips status to `FAILED`, commits, then enqueues
`app/services/calls/vobiz.py:trigger_recovery_call` via FastAPI
`BackgroundTasks`. The trigger calls Vobiz `POST /Account/{auth_id}/Call/`
with `from` = `VOBIZ_CALLER_ID`, `to` = customer phone, `answer_url` =
`VOBIZ_ANSWER_URL`. Before dialing, it persists a `CallAttempt` claim unique
to the merchant and payment, then records the provider ID and placement
status. Without credentials it logs `skipped:vobiz-not-configured` and the
webhook still returns 2xx. Covered by `apps/backend/tests/test_call_trigger.py`.

## Rule

```text
FAILED transition + customer phone present + no existing call attempt for this payment = CALL
Everything else = DO NOT CALL
```

## Webhook event -> call decision

| Stripe event | Call? | Why |
|---|---|---|
| `payment_intent.payment_failed` | YES | Core failed-payment case. Currently the only failure event that sets `FAILED` (`webhooks.py:661`). |
| `checkout.session.expired` | YES (when wired) | Abandoned checkout. Architecture lists it as `FAILED`, but code currently ignores it (`STORED_EVENT_TYPES` allowlist). Wire it before calling. |
| `checkout.session.async_payment_failed` | YES (when wired) | Same as above — listed as `FAILED`, currently ignored. |
| `invoice.payment_failed` / `invoice_payment.failed` | YES (when wired) | Subscription renewal failed. Listed as `FAILED`, currently ignored. |
| `charge.failed` | NO by default | Noisy, usually pairs with a `payment_intent.payment_failed` for the same attempt. Calling on both = double calls. Only revisit if PI event is missing. |
| `payment_intent.succeeded` | NO | Success — close any open call as recovered instead. |
| `checkout.session.completed` (paid/complete) | NO | Success — currently the only `COMPLETED` path in code (`webhooks.py:674`). |
| `invoice.paid` / `invoice_payment.paid` | NO | Success — same close-as-recovered behavior once wired. |
| `account.application.deauthorized` | NO | Merchant disconnected. Deletes merchant Stripe data, nothing to call about. |
| Duplicate / unknown account / bad signature | NO | Never call on untrusted or duplicate events. |

## Guardrails (v1)

1. Phone required — no `customer_phone` on the payment event, no call.
2. One call per payment — dedupe on `payment_id`; repeat failure webhooks for the same payment do not re-call.
3. Success wins — any later `COMPLETED` for the same payment cancels/closes the call job.
4. Async only — webhook returns 2xx fast; call job runs in a worker with its own retry, not webhook retry.
5. Merchant scope — job carries `merchant_id` from the resolved `ProviderConnection`; never resolve merchant from metadata/phone.

## Next trigger extension

Code today only stores `checkout.session.completed` + `payment_intent.payment_failed` (`STORED_EVENT_TYPES`, `webhooks.py:41`). The other rows above match `docs/architecture.md` intent but are ignored at `webhooks.py:583`. Extend the allowlist + `FAILED`/`COMPLETED` transitions first, then attach the call enqueue behind the same transition so every call source stays `Payment.status = FAILED`.
