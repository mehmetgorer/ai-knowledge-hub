# AI Knowledge Hub

**Ask questions about your documents and get AI-generated answers with source references.**

AI Knowledge Hub is a full-stack application for organizing documents, searching their content, and asking questions using locally running AI models. There is no public hosted deployment; you run the web app, API, database, embedding model, and Ollama on your own machine.

Repository: [github.com/mehmetgorer/ai-knowledge-hub](https://github.com/mehmetgorer/ai-knowledge-hub)

## Preview

Add PNG captures under [`docs/screenshots/`](docs/screenshots/) (see checklist in that folder). When the files below exist, they render on GitHub:

| Screenshot | File |
| ---------- | ---- |
| Ask AI with citations | `docs/screenshots/ask-ai.png` |
| Semantic search results | `docs/screenshots/semantic-search.png` |
| Document list and statuses | `docs/screenshots/documents.png` |
| Mobile Ask AI (375px) | `docs/screenshots/mobile-ask.png` |
| Mobile documents (375px) | `docs/screenshots/mobile-documents.png` |

Example embed once captured:

```markdown
![Ask AI answering a question with source references](docs/screenshots/ask-ai.png)
```

## Screenshots

Gallery files (capture locally; do not commit secrets or private data):

1. **`ask-ai.png`** — Desktop Ask AI with a successful grounded answer and visible PDF (or document) source citation.
2. **`semantic-search.png`** — Desktop Semantic Search showing real retrieved passages and scores.
3. **`documents.png`** — Desktop Documents tab with uploaded files and status badges (e.g. Ready, Processed).
4. **`mobile-ask.png`** — Ask AI at **375px** viewport width.
5. **`mobile-documents.png`** — Document cards at **375px** width.

Optional: **`ask-abstention.png`** — Ask response that safely abstains when evidence is weak.

## What it does

- **Collections** — Sign in and keep documents in private collections tied to your account.
- **Upload** — Add PDF, plain text, or Markdown files with size and type checks.
- **Process and index** — Extract text, split into chunks, embed with a multilingual model, and store vectors in PostgreSQL for search.
- **Semantic search** — Find relevant passages by meaning, not just keywords.
- **Ask AI** — Get a short answer grounded in retrieved passages, with source IDs the app validates against real chunks (or a safe abstention when evidence is insufficient).

## Main workflows

After you sign in at `/dashboard`, use the tabs:

1. **Ask AI** — Ask a question; the API retrieves chunks, calls Ollama, and returns an answer plus sources when grounding checks pass.
2. **Semantic Search** — Enter a query and inspect ranked passages with distance scores.
3. **Documents** — Upload files, run **Process** and **Index**, and delete when allowed by document status.

On narrow screens, the document list switches to cards; the desktop table layout is unchanged from tablet width upward.

## How it works (RAG pipeline)

In plain terms, the system does not send your whole library to the language model. It finds a small set of relevant pieces first, then asks the model to answer using only those pieces.

```
Upload (PDF / TXT / MD)
  → text extraction
  → chunking
  → multilingual E5 embeddings (intfloat/multilingual-e5-small)
  → stored in PostgreSQL with pgvector
  → semantic search for the question
  → Ollama (default qwen3:1.7b) produces a structured JSON answer
  → citation and grounding validation
  → answer with source references, or abstention
```

**Authentication** — Neon Auth issues JWTs; the Next.js app sends them to FastAPI, which resolves the user subject and enforces collection ownership on every protected route.

**Citations** — The API validates that cited source IDs and support quotes match retrieved evidence. That reduces unsupported claims and invented references; it does **not** guarantee full semantic fact-checking of every statement.

**Document lifecycle** — Statuses include uploaded, processing, processed, indexing, ready, and failed. Search and Ask use **ready** documents only. Delete is blocked while processing or indexing.

## Tech stack

| Layer | Technology |
| ----- | ------------ |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Auth | Neon Auth (`@neondatabase/auth`), JWT to API |
| API | Python 3.12, FastAPI, SQLAlchemy 2, psycopg 3, uv |
| Database | PostgreSQL 17, pgvector, Alembic migrations |
| Embeddings | Sentence Transformers, `intfloat/multilingual-e5-small` (local CPU) |
| Answers | Ollama, default `qwen3:1.7b` (local, server-side only) |

## Architecture

```
┌─────────────┐     JWT      ┌──────────────┐     SQL/pgvector   ┌────────────┐
│  apps/web   │ ───────────► │ services/api │ ◄──────────────► │ PostgreSQL │
│  Next.js    │   REST       │   FastAPI    │                  │  + pgvector│
└─────────────┘              └──────┬───────┘                  └────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             Local file storage   E5 embed      Ollama HTTP
             (document bytes)     (in-process)  (RAG answers)
```

The dashboard loads collections once in the shell; workspace panels share document state and guard against stale UI when you switch collections or tabs.

## Testing and quality

[![CI](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml)

GitHub Actions on `main` runs three jobs:

- **Frontend** — lint, typecheck, unit tests, production build
- **Backend** — Ruff, unit pytest (no database)
- **Backend integration (PostgreSQL)** — pytest integration suite against ephemeral `alembic_test_*` databases with pgvector

See [`docs/QUALITY_AUDIT.md`](docs/QUALITY_AUDIT.md) for the Phase 5D security and lifecycle audit. Phase 5D includes atomic document delete guards and isolation regression tests.

### Run checks locally

```powershell
# Frontend (repo root)
npm run lint
npm run typecheck
npm run test --workspace=web
npm run build

# Backend (services/api)
uv run ruff check .
uv run pytest
uv run pytest -m integration   # requires local Docker Postgres
```

## Local setup

You need Node.js, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker for PostgreSQL, [Ollama](https://ollama.com) for Ask AI, and Neon Auth configuration for sign-in. Do not commit `.env` or `.env.local`.

### 1. PostgreSQL

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up -d
```

Default host port is **5433** (`POSTGRES_PORT` in `.env`). The API uses Postgres for collections, documents, chunks, embeddings, and health checks—not only liveness probes.

### 2. API

```powershell
cd services\api
uv sync
Copy-Item .env.example .env
# Set AUTH_JWKS_URL, AUTH_ISSUER, AUTH_AUDIENCE (see .env.example comments)
uv run alembic upgrade head
uv run ai-knowledge-hub-api
```

API default: [http://localhost:8000](http://localhost:8000)

On first use, the embedding model downloads via Sentence Transformers (CPU). Configure Ollama in `services/api/.env` (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, timeouts) and run:

```powershell
ollama pull qwen3:1.7b
```

### 3. Web app

```powershell
# repo root
npm install
cd apps\web
Copy-Item .env.example .env.local
# Set NEON_AUTH_BASE_URL, NEON_AUTH_COOKIE_SECRET (≥32 chars), NEXT_PUBLIC_API_BASE_URL
cd ..\..
npm run dev
```

App: [http://localhost:3000](http://localhost:3000) — sign up or sign in, then open **Dashboard**.

### Project layout

```
.
├── apps/web/           # Next.js dashboard
├── services/api/       # FastAPI, Alembic, RAG pipeline
├── docker-compose.yml  # PostgreSQL 17 + pgvector
├── docs/               # HANDOFF, QUALITY_AUDIT, screenshots
└── package.json        # npm workspace root
```

Further phase history: [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Known limitations

- **Local only** — No production deployment is included in this repository.
- **Stuck jobs** — If the API stops during processing or indexing, a document may remain in that status until you intervene manually.
- **Orphan files** — Rarely, a database row can be removed while a file remains on disk; see audit notes in `docs/QUALITY_AUDIT.md`.
- **Grounding** — Citation validation is structural; answers can still be wrong or incomplete in edge cases.
- **Scale** — Synchronous process/index on the API process; no distributed queue or multi-tenant ops hardening.
- **CI** — Integration tests use real Postgres in Actions; Ask AI in CI uses mocked Ollama, not live `qwen3:1.7b`.

## License

See repository defaults; treat credentials and uploaded content as local-only.
