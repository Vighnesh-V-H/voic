# Voic monorepo — frontend (Next.js), backend (FastAPI), migrations (Alembic)
#
# Usage from repo root:
#   make backend        # run backend + stripe listen + ngrok in parallel
#   make backend-serve  # run FastAPI with uvicorn --reload only (apps/backend)
#   make backend-stripe # forward Stripe Connect webhooks to localhost:8000
#   make backend-ngrok  # expose localhost:8000 via ngrok
#   make frontend       # run Next.js dev server (apps/frontend)
#   make dev            # run both backend + frontend in parallel (make -j2)
#   make migrate        # alembic upgrade head (apps/backend)
#   make migration msg="add payments table"   # new autogenerate revision
#
# Backend commands run from apps/backend so alembic.ini and `app.*`
# imports resolve. Frontend commands use `npm --prefix` so no `cd` needed.

.DEFAULT_GOAL := help

BACKEND_DIR := apps/backend
FRONTEND_DIR := apps/frontend

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000

# Local webhook forwarding (kept in sync with BACKEND_PORT).
# Uses --forward-connect-to so Stripe preserves the connected-account envelope.
STRIPE_FORWARD_TO ?= localhost:$(BACKEND_PORT)/api/v1/webhooks/stripe

# venv python, relative to BACKEND_DIR (recipes `cd` there first).
ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
else
PYTHON := .venv/bin/python
endif

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

# ---- install ----

.PHONY: install backend-install frontend-install
install: backend-install frontend-install ## Install backend + frontend deps

backend-install: ## pip install backend (editable + test extras) into apps/backend/.venv
	cd $(BACKEND_DIR) && python -m venv .venv
	cd $(BACKEND_DIR) && "$(PYTHON)" -m pip install -e ".[test]"

frontend-install: ## npm install for apps/frontend
	npm --prefix $(FRONTEND_DIR) install

# ---- run ----

.PHONY: backend backend-serve backend-stripe backend-ngrok frontend dev
backend-serve: ## Run FastAPI backend only (uvicorn --reload)
	cd $(BACKEND_DIR) && "$(PYTHON)" -m uvicorn app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

backend-stripe: ## Forward Stripe Connect webhooks to local backend (requires stripe CLI)
	stripe listen --forward-connect-to $(STRIPE_FORWARD_TO)

backend-ngrok: ## Expose local backend via ngrok (requires ngrok)
	ngrok http $(BACKEND_PORT)

backend: ## Run backend + Stripe forwarding + ngrok together in parallel
	$(MAKE) -j3 backend-serve backend-stripe backend-ngrok

frontend: ## Run Next.js frontend dev server
	npm --prefix $(FRONTEND_DIR) run dev

dev: ## Run backend + frontend together in parallel
	$(MAKE) -j2 backend frontend

# ---- migrations (alembic, always from apps/backend) ----

.PHONY: migrate migrate-up migrate-down migration migrate-history migrate-current migrate-heads migrate-check migrate-sql
migrate: migrate-up ## Apply all pending migrations (alembic upgrade head)

migrate-up: ## alembic upgrade head
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic upgrade head

migrate-down: ## Roll back one migration (alembic downgrade -1)
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic downgrade -1

migration: ## New autogenerate revision: make migration msg="describe change"
ifndef msg
	$(error msg is required, e.g. make migration msg="add payments table")
endif
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic revision --autogenerate -m "$(msg)"

migrate-history: ## Show migration history
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic history

migrate-current: ## Show current DB revision
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic current

migrate-heads: ## Show latest revision heads
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic heads

migrate-check: ## Check autogenerate diff without writing a file
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic check

migrate-sql: ## Print pending migrations as SQL without applying them
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic upgrade head --sql

# ---- verify (mirrors AGENTS.md) ----

.PHONY: backend-test frontend-lint frontend-build verify
backend-test: ## pytest from apps/backend
	cd $(BACKEND_DIR) && "$(PYTHON)" -m pytest -q

frontend-lint: ## eslint for apps/frontend
	npm --prefix $(FRONTEND_DIR) run lint

frontend-build: ## production build for apps/frontend
	npm --prefix $(FRONTEND_DIR) run build

verify: backend-test frontend-lint frontend-build migrate-sql ## Backend tests + frontend lint/build + offline migration SQL
