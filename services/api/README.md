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

| Revision | Purpose |
| -------- | ------- |
| `0001_enable_vector` | `CREATE EXTENSION IF NOT EXISTS vector` (downgrade does not drop extension) |
| `0002_collections_documents` | `collections` and `documents` tables |
| `0003_document_chunks` | `document_chunks` table |
| `0004_document_status_processed` | `DocumentStatus.PROCESSED` enum value |
| `0005_document_chunk_embeddings` | nullable pgvector columns on `document_chunks` |
| `0006_document_status_indexing` | `DocumentStatus.INDEXING` enum value |

ORM models live in `src/ai_knowledge_hub_api/models/`. `Collection.owner_subject` must come from a **verified** identity provider in production, not from unauthenticated client input (see model docstring).

## Run

```powershell
uv run ai-knowledge-hub-api
```

| Endpoint | Description |
| -------- | ----------- |
| `GET /health/live` | Process liveness (no database) |
| `GET /health/ready` | `SELECT 1` against PostgreSQL; `503` if unreachable |
| `GET /auth/me` | Verified JWT subject (`Authorization: Bearer`); requires `AUTH_JWKS_URL` + `AUTH_ISSUER` |

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

Last verified: **30 passed**, 3 deselected (`integration`).

PostgreSQL integration (requires `docker compose up -d` from repo root):

```powershell
uv run pytest -m integration
```

Last verified: **3 passed**, 17 deselected (connectivity, Alembic, schema constraints on temporary databases).

If Postgres is unreachable, the integration test **fails** (no skip).
