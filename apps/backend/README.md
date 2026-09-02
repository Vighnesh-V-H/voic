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
