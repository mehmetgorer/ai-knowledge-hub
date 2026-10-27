# Handoff — AI Knowledge Hub

## Repository

- **GitHub:** https://github.com/mehmetgorer/ai-knowledge-hub
- **Default branch:** `main`

## Phase 1A — Frontend foundation (complete)

- npm workspaces with `apps/web` (Next.js 16, TypeScript, Tailwind CSS v4, ESLint).
- Minimal home page and root npm scripts: `dev`, `build`, `lint`, `typecheck`.

## Phase 1B — FastAPI foundation (complete)

- Independent Python project at `services/api` (Python 3.12+, **uv**).
- FastAPI, Pydantic Settings, Uvicorn, Ruff, pytest, httpx.
- `GET /health/live` — liveness without database.

## Phase 1C — Local database infrastructure (complete)

- Root `docker-compose.yml` — PostgreSQL 17 + pgvector (`pgvector/pgvector:0.8.7-pg17`).
- Named volume `ai-knowledge-hub-postgres-data`, port `127.0.0.1:5433` by default.
- Root `.env.example` for `POSTGRES_*`; `scripts/postgres-smoke-test.sql`.

## Phase 1D.1 — Database connection (complete)

- **SQLAlchemy 2.x** + **psycopg 3** in `services/api`.
- `ai_knowledge_hub_api.database` — engine singleton, `ping_database()` (`SELECT 1`), `dispose_engine()` on app shutdown.
- Settings load repo root `.env` then `services/api/.env`; reuse `POSTGRES_*` or optional `DATABASE_URL`; `SecretStr` for passwords; `DATABASE_CONNECT_TIMEOUT` (default 5s).
- `GET /health/ready` — `200` when DB reachable, `503` with safe JSON when not; `/health/live` unchanged.
- Tests: mocked ready success/failure; config URL building; optional `integration` marker test against Docker Postgres.

## Phase 1D.1a — Test isolation (complete)

- pytest `integration` marker registered; default `uv run pytest` uses `--strict-markers` and `-m "not integration"`.
- Explicit integration run: `uv run pytest -m integration` (fails if Postgres is down).

**Not in scope:** Alembic, ORM models, app tables, auth, RAG.

### Verification

```powershell
# Postgres (repo root)
docker compose up -d

# API (services/api)
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest              # unit: 9 passed, 1 deselected
uv run pytest -m integration # integration: 1 passed (with Docker Postgres)
uv run ai-knowledge-hub-api
# GET http://localhost:8000/health/live
# GET http://localhost:8000/health/ready

# Frontend (repo root)
npm run lint
npm run typecheck
npm run build
```

## Explicitly not in scope yet

- Alembic migrations and SQLAlchemy models.
- Authentication, embeddings, RAG, document uploads, external AI APIs.
- CI workflows.

## Recommended next steps (Phase 1D.2+)

1. Alembic bootstrap and first migration workflow.
2. GitHub Actions with pytest (unit) and optional compose job for integration.
3. Shared `DATABASE_URL` documentation for managed Postgres.

## Notes

- Frontend unchanged in Phase 1D.1.
- Never log or return database credentials from the API.
