# AI Knowledge Hub API

FastAPI backend for AI Knowledge Hub.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
cd services/api
uv sync
```

Copy `.env.example` to `.env` for API-specific settings. Database credentials are read from the **repository root** `.env` (`POSTGRES_*`) when present; optional `DATABASE_URL` overrides the built URL.

Start local PostgreSQL from the repo root (`docker compose up -d`) before readiness checks.

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

Last verified: **9 passed**, 1 deselected (`integration`).

PostgreSQL integration (requires `docker compose up -d` from repo root):

```powershell
uv run pytest -m integration
```

Last verified: **1 passed**, 9 deselected (Docker Postgres on `127.0.0.1:5433`).

If Postgres is unreachable, the integration test **fails** (no skip).
