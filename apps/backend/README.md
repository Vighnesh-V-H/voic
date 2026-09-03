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

## PayPal Sandbox setup

This branch uses PayPal's standard REST app authentication for development. It does not use a PayPal merchant redirect callback; the backend exchanges the app's client ID and secret for a short-lived `client_credentials` access token.

The connection is associated with the authenticated Voic merchant for testing, but standard app OAuth authorizes the configured Sandbox REST app rather than a separate external PayPal merchant account. Separate seller-account authorization would require PayPal's Multiparty partner flow.

1. Sign in to the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/), switch to **Sandbox**, and create a REST app.
2. Copy the app's client ID and secret into `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in `.env`.
3. Generate an encryption key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set it as `TOKEN_ENCRYPTION_KEY`.
4. Keep `PAYPAL_API_BASE_URL` set to `https://api-m.sandbox.paypal.com`.
5. Start the frontend and backend, sign up or log in, open `/settings/integrations`, and click **Connect PayPal Sandbox**.
6. Open the payment tester, create an order, approve it using a PayPal Sandbox personal account, and return to Voic to capture the payment.

The PayPal credentials and access token remain server-side. The browser receives only connection and payment status data.
