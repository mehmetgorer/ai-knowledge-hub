# Handoff — AI Knowledge Hub

## Repository

- **GitHub:** https://github.com/mehmetgorer/ai-knowledge-hub
- **Default branch:** `main`

## Phase 1A–1C — Summary

- Frontend (`apps/web`), FastAPI API (`services/api`), local Docker PostgreSQL 17 + pgvector.

## Phase 1D.1 / 1D.1a — Database connection & test isolation (complete)

- SQLAlchemy 2 + psycopg 3; `/health/ready`; pytest `integration` marker excluded from default runs.

## Phase 1D.2 — Alembic migrations (complete)

- **Alembic** in `services/api` (`alembic.ini`, `alembic/env.py`, `alembic/versions/`).
- `env.py` uses `get_settings().resolved_database_url` (no credentials in `alembic.ini`; safe for `%` in passwords).
- Revision **`0001_enable_vector`**: `CREATE EXTENSION IF NOT EXISTS vector`; downgrade is a no-op (extension not dropped).
- No application tables or ORM models yet.

### Alembic commands (from `services/api`)

```powershell
uv run alembic upgrade head
uv run alembic current
uv run alembic history
uv run alembic downgrade base
```

### Verification

```powershell
# Postgres (repo root)
docker compose up -d

# API (services/api)
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest                    # unit: 14 passed, 2 deselected
uv run pytest -m integration     # integration: 2 passed, 14 deselected
uv run alembic upgrade head      # idempotent on main DB

# Frontend (repo root)
npm run lint
npm run typecheck
npm run build
```

Integration tests include Alembic upgrade/downgrade on a **temporary** database (created and dropped in the test; main DB volume untouched).

## Phase 1D.2a — Alembic test safety (complete)

- Alembic integration subprocesses set explicit `DATABASE_URL` for the temporary database (overrides `.env`).
- Destructive integration tests require local `POSTGRES_HOST` and `alembic_test_*` database names; main app DB revision is checked unchanged after the test.

## Phase 1E — GitHub Actions CI (complete)

- Workflow `.github/workflows/ci.yml` on `push` / `pull_request` to `main`.
- Jobs: **Frontend** (Node 24, `npm ci`, lint, typecheck, build) and **Backend** (`services/api`, `uv sync --frozen`, lock check, Ruff, unit pytest).
- `permissions: contents: read`; no secrets, Docker, or integration tests in CI.

## Explicitly not in scope yet

- SQLAlchemy ORM models and application tables.
- Authentication, embeddings, RAG, document uploads, external AI APIs.
- CI jobs for Docker / PostgreSQL integration tests.

## Recommended next steps

1. First application schema migration(s) when models are defined.
2. Optional scheduled or manual workflow for `pytest -m integration` with Docker.
3. Document production `DATABASE_URL` for managed Postgres.

## Notes

- Frontend unchanged in Phase 1D.2.
- Never log or return database credentials from the API or Alembic.
