# AI Knowledge Hub API

FastAPI backend for AI Knowledge Hub.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
cd services/api
uv sync
```

Copy `.env.example` to `.env` for API-specific settings. Database credentials are read from the **repository root** `.env` (`POSTGRES_*`) when present; optional `DATABASE_URL` overrides the built URL.

Start local PostgreSQL from the repo root (`docker compose up -d`) before readiness checks and migrations.

## Database migrations (Alembic)

From `services/api` (uses the same Settings / root `.env` as the API):

```powershell
uv run alembic upgrade head
uv run alembic current
uv run alembic history
uv run alembic downgrade base
```

Initial revision `0001_enable_vector` runs `CREATE EXTENSION IF NOT EXISTS vector`. Downgrade does **not** drop the extension (see migration docstring).

## Run

```powershell
uv run ai-knowledge-hub-api
```

| Endpoint | Description |
| -------- | ----------- |
| `GET /health/live` | Process liveness (no database) |
| `GET /health/ready` | `SELECT 1` against PostgreSQL; `503` if unreachable |

## Quality checks

```powershell
uv run ruff check .
uv run ruff format --check .
```

### Tests

Default (unit only, no PostgreSQL required):

```powershell
uv run pytest
```

Last verified: **9 passed**, 2 deselected (`integration`).

PostgreSQL integration (requires `docker compose up -d` from repo root):

```powershell
uv run pytest -m integration
```

Last verified: **2 passed**, 9 deselected (connectivity + Alembic on a temporary database).

If Postgres is unreachable, the integration test **fails** (no skip).
