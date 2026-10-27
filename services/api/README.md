# AI Knowledge Hub API

FastAPI backend for AI Knowledge Hub (Phase 1B foundation).

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
cd services/api
uv sync
```

Copy `.env.example` to `.env` and adjust values as needed.

## Run

```powershell
uv run ai-knowledge-hub-api
```

Health check: `GET http://localhost:8000/health/live`

## Quality checks

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
