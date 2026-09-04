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
