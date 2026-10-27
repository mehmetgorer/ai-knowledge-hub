# AI Knowledge Hub

Independent, professional AI-powered document intelligence platform.

Repository: [github.com/mehmetgorer/ai-knowledge-hub](https://github.com/mehmetgorer/ai-knowledge-hub)

## Stack

| Area | Location | Stack |
| ---- | -------- | ----- |
| Frontend | `apps/web` | Next.js (App Router), TypeScript, Tailwind CSS, ESLint |
| API | `services/api` | Python 3.12, FastAPI, Pydantic Settings, Uvicorn, uv |

Python and npm dependencies are managed independently.

## Prerequisites

- Node.js 20+ and npm 10+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

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
cd services\api
uv sync
Copy-Item .env.example .env
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
Health: `GET /health/live`

CORS allows origins from `CORS_ORIGINS` (comma-separated). Default: `http://localhost:3000`.

## Project layout

```
.
├── apps/
│   └── web/              # Next.js frontend
├── services/
│   └── api/              # FastAPI backend
├── docs/
│   └── HANDOFF.md
├── package.json          # npm workspace root
└── package-lock.json
```

See `docs/HANDOFF.md` for phase status and next steps.
