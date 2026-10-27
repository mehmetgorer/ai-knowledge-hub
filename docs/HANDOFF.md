# Handoff — AI Knowledge Hub

## Repository

- **GitHub:** https://github.com/mehmetgorer/ai-knowledge-hub
- **Default branch:** `main`

## Phase 1A — Frontend foundation (complete)

- npm workspaces with `apps/web` (Next.js 16, TypeScript, Tailwind CSS v4, ESLint).
- Minimal home page and root npm scripts: `dev`, `build`, `lint`, `typecheck`.
- Published to GitHub (initial commit on `main`).

## Phase 1B — FastAPI foundation (complete)

- Independent Python project at `services/api` (Python 3.12+, managed with **uv**).
- **FastAPI** app with **Pydantic Settings**, **Uvicorn**, **Ruff**, **pytest**, **httpx**.
- Package layout: `src/ai_knowledge_hub_api/` (`app`, `config`, `routers`, `schemas`, `main`).
- `GET /health/live` — JSON `{ "service": "<SERVICE_NAME>", "status": "healthy" }`.
- **CORS** middleware with explicit allowlist from `CORS_ORIGINS` (default `http://localhost:3000`).
- `services/api/.env.example` (no secrets); local `.env` gitignored.
- Tests: health endpoint and settings/CORS parsing.
- `uv.lock` committed for reproducible installs.

## Phase 1C — Local database infrastructure (complete)

- Root `docker-compose.yml` — PostgreSQL 17 + pgvector (`pgvector/pgvector:0.8.7-pg17`).
- Named volume `ai-knowledge-hub-postgres-data`, health check, `restart: unless-stopped`, `stop_grace_period: 30s`.
- Port `127.0.0.1:${POSTGRES_PORT:-5433}` → container `5432`.
- Root `.env.example` with development-only placeholder DB credentials; `.env` gitignored.
- `scripts/postgres-smoke-test.sql` — connectivity, version, pgvector availability, `CREATE EXTENSION vector`.
- **Not in scope:** SQLAlchemy, Alembic, models, FastAPI DB connection.

### Database verification (from repo root)

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d
docker compose ps
Get-Content scripts\postgres-smoke-test.sql | docker compose exec -T postgres psql -U ai_knowledge_hub -d ai_knowledge_hub
```

Use `docker compose down` or `docker compose stop` to shut down; do **not** use `docker compose down -v` unless you intend to delete the named volume.

### API verification (from `services/api`)

```powershell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

### Frontend verification (from repo root)

```powershell
npm run lint
npm run typecheck
npm run build
```

## Explicitly not in scope yet

- SQLAlchemy, Alembic, ORM models, API database wiring.
- Authentication, embeddings, RAG, document uploads, external AI APIs.
- CI workflows (recommended next).

## Recommended next steps (Phase 1D+)

1. SQLAlchemy + Alembic in `services/api` with settings-driven `DATABASE_URL`.
2. GitHub Actions: Docker-less API/frontend checks + optional compose integration job.
3. Migrations and first persistence models when product schema is defined.

## Notes

- `apps/web/AGENTS.md` is Next.js scaffold guidance; optional to keep.
- API and frontend application code unchanged in Phase 1C (docs and infra only).
