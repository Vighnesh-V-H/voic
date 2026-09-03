# Voic Makefile — Windows (PowerShell/msys) + POSIX compatible
# Usage from repo root: make <target>
# Requires: GNU Make (C:\msys64\usr\bin\make.exe), Python 3.12+, Node 18+, PostgreSQL
# Shell is /bin/sh (msys) when invoked via C:\msys64\usr\bin\make.exe — don't use PowerShell-only syntax.

# Detect OS for venv python path
# PYTHON       = repo-root-relative, used when running from repo root (install targets)
# BACKEND_PYTHON = backend-relative, used after `cd apps/backend` (run/test/migrate targets)
ifeq ($(OS),Windows_NT)
  PYTHON         := apps/backend/.venv/Scripts/python.exe
  BACKEND_PYTHON := .venv/Scripts/python.exe
else
  PYTHON         := apps/backend/.venv/bin/python
  BACKEND_PYTHON := .venv/bin/python
endif

PIP      := $(PYTHON) -m pip
PYTEST   := $(PYTHON) -m pytest
UVICORN  := $(PYTHON) -m uvicorn
ALEMBIC  := $(PYTHON) -m alembic
COMPILE  := $(PYTHON) -m compileall

# Backend-relative variants (must be used after `cd $(BACKEND_DIR)`)
BACKEND_PYTEST  := $(BACKEND_PYTHON) -m pytest
BACKEND_UVICORN := $(BACKEND_PYTHON) -m uvicorn
BACKEND_ALEMBIC := $(BACKEND_PYTHON) -m alembic
BACKEND_COMPILE := $(BACKEND_PYTHON) -m compileall

BACKEND_DIR  := apps/backend
FRONTEND_DIR := apps/frontend

.PHONY: help install install-backend install-frontend backend frontend dev test test-backend test-frontend lint build migrate migrate-sql compile clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────────────────
install: install-backend install-frontend ## Install backend + frontend deps

install-backend: ## Create venv (if missing) and install backend deps
	@if [ ! -f "$(PYTHON)" ]; then echo "Creating venv..."; python -m venv $(BACKEND_DIR)/.venv; fi
	$(PIP) install -e "$(BACKEND_DIR)/.[test]"

install-frontend: ## Install frontend deps
	npm --prefix $(FRONTEND_DIR) install

# ── Run ──────────────────────────────────────────────────────────────
backend: ## Run backend dev server (http://localhost:8000, reload)
	cd $(BACKEND_DIR) && $(BACKEND_UVICORN) app.main:app --reload  --port 8000

frontend: ## Run frontend dev server (http://localhost:3000)
	npm --prefix $(FRONTEND_DIR) run dev

dev: ## Print how to run both (make can't parallelize reliably on Windows)
	@echo "Run in two terminals:"
	@echo "  make backend   # terminal 1 — FastAPI on :8000"
	@echo "  make frontend  # terminal 2 — Next.js on :3000"

# ── Test / Verify ──────────────────────────────────────────────────
test: test-backend test-frontend ## Run all checks (backend pytest + frontend lint+build)

test-backend: ## Run backend tests (pytest -q)
	cd $(BACKEND_DIR) && $(BACKEND_PYTEST) -q

test-frontend: ## Run frontend lint + build
	npm --prefix $(FRONTEND_DIR) run lint
	npm --prefix $(FRONTEND_DIR) run build

lint: ## Lint frontend only
	npm --prefix $(FRONTEND_DIR) run lint

build: ## Build frontend only
	npm --prefix $(FRONTEND_DIR) run build

compile: ## Byte-compile backend (syntax check)
	cd $(BACKEND_DIR) && $(BACKEND_COMPILE) -q app migrations tests

# ── DB ───────────────────────────────────────────────────────────────
migrate: ## Apply alembic migrations (needs DATABASE_URL / running Postgres)
	cd $(BACKEND_DIR) && $(BACKEND_ALEMBIC) upgrade head

migrate-sql: ## Print SQL for pending migrations (offline, no DB needed)
	cd $(BACKEND_DIR) && $(BACKEND_ALEMBIC) upgrade head --sql

# ── Clean ────────────────────────────────────────────────────────────
clean: ## Remove caches / build artifacts
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/voic_backend.egg-info
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/node_modules/.cache
	find $(BACKEND_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
