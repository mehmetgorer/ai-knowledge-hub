# AI Knowledge Hub

Independent, professional AI-powered document intelligence platform.

Repository: [github.com/mehmetgorer/ai-knowledge-hub](https://github.com/mehmetgorer/ai-knowledge-hub)

## Stack

| Area | Location | Stack |
| ---- | -------- | ----- |
| Frontend | `apps/web` | Next.js (App Router), TypeScript, Tailwind CSS, ESLint |
| API | `services/api` | Python 3.12, FastAPI, SQLAlchemy 2, psycopg 3, uv |
| Database (local) | Docker Compose | PostgreSQL 17 + pgvector |

Python and npm dependencies are managed independently.

## Prerequisites

- Node.js 20+ and npm 10+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2) for local PostgreSQL

### Install uv (Windows)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Add uv to your session if needed:

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
```

## Frontend (`apps/web`)

From the repository root:

| Command | Description |
| ------- | ----------- |
| `npm install` | Install Node dependencies |
| `npm run dev` | Next.js dev server |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | Production build |

Dev URL: [http://localhost:3000](http://localhost:3000)

## API (`services/api`)

```powershell
# From repo root: ensure root .env exists for POSTGRES_* (see .env.example)
cd services\api
uv sync
Copy-Item .env.example .env   # optional API-only settings
uv run ai-knowledge-hub-api
```

| Command | Description |
| ------- | ----------- |
| `uv sync` | Install dependencies from `uv.lock` |
| `uv run ai-knowledge-hub-api` | Start Uvicorn |
| `uv run ruff check .` | Lint |
| `uv run ruff format --check .` | Format check |
| `uv run pytest` | API tests |

API base URL (default): [http://localhost:8000](http://localhost:8000)

| Endpoint | Description |
| -------- | ----------- |
| `GET /health/live` | Liveness (no database) |
| `GET /health/ready` | Database connectivity (`SELECT 1`); `503` if Postgres is down |

Database URL is built from root `POSTGRES_*` variables or optional `DATABASE_URL`. Settings load `../../.env` then `services/api/.env` when you run commands from `services/api`.

CORS allows origins from `CORS_ORIGINS` (comma-separated). Default: `http://localhost:3000`.

## Local PostgreSQL (Docker)

PostgreSQL 17 with **pgvector** for local development. The API connects for `/health/ready` only (no migrations or app tables yet).

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d
docker compose ps
```

| Command | Description |
| ------- | ----------- |
| `docker compose up -d` | Start Postgres (detached) |
| `docker compose ps` | Status and health |
| `docker compose logs postgres` | Container logs |
| `docker compose exec postgres pg_isready -U ai_knowledge_hub -d ai_knowledge_hub` | Readiness probe |
| `Get-Content scripts\postgres-smoke-test.sql \| docker compose exec -T postgres psql -U ai_knowledge_hub -d ai_knowledge_hub` | SQL smoke test |
| `docker compose stop` | Stop containers (keeps data volume) |
| `docker compose down` | Stop and remove containers (keeps named volume) |

- **Image:** `pgvector/pgvector:0.8.7-pg17`
- **Host:** `127.0.0.1` — **Port:** `5433` by default (`POSTGRES_PORT` in `.env`)
- **Volume:** `ai-knowledge-hub-postgres-data` (persistent; not removed by `docker compose down`)

Use credentials from your local `.env` (see `.env.example`). Never commit `.env`.

## Project layout

```
.
├── apps/
│   └── web/              # Next.js frontend
├── services/
│   └── api/              # FastAPI backend
├── scripts/
│   └── postgres-smoke-test.sql
├── docker-compose.yml    # Local PostgreSQL + pgvector
├── docs/
│   └── HANDOFF.md
├── package.json          # npm workspace root
└── package-lock.json
```

See `docs/HANDOFF.md` for phase status and next steps.
