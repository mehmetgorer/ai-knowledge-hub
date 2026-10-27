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
- Root `.gitignore` extended for Python virtualenvs and caches.

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

- PostgreSQL, Docker, SQLAlchemy, Alembic.
- Authentication, embeddings, RAG, document uploads, external AI APIs.
- CI workflows (recommended next).

## Recommended next steps (Phase 1C+)

1. Add GitHub Actions: npm lint/typecheck/build + uv ruff/pytest.
2. Shared API contract or OpenAPI export for frontend integration.
3. Database layer and migrations when persistence is required.
4. Optional: root `docker-compose` only after Docker phase is approved.

## Notes

- `apps/web/AGENTS.md` is Next.js scaffold guidance; optional to keep.
- Frontend was not changed in Phase 1B except documentation at repo root.
