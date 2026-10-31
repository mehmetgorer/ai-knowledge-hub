# AI Knowledge Hub

**English** | [Türkçe](README.tr.md)

Search your documents and ask questions with answers linked to their sources.

Upload PDF, TXT, or Markdown files into your own collections, run semantic search over the indexed text, and use **Ask AI** to get short answers backed by retrieved passages. Inference runs on your machine (embeddings + Ollama)—there is no hosted demo in this repo.

![Ask AI answering a Turkish question about backend stack with a citation to rag-test.pdf](docs/screenshots/ask-ai-grounded-answer.png)

## What it does

- **Collections** — Sign in with Neon Auth; collections and documents are scoped to your account (JWT on each API call).
- **Upload** — PDF, TXT, or Markdown with size and MIME checks.
- **Process & index** — Extract text, chunk it, embed with **`intfloat/multilingual-e5-small`** (384-d vectors), store in **PostgreSQL + pgvector**.
- **Semantic search** — Rank chunks by cosine distance within a collection. *(Not pictured below; Ask AI uses the same retrieval path.)*
- **Ask AI** — Retrieve top passages, call **Ollama (`qwen3:1.7b`)**, validate cited source IDs and support quotes, then return an answer or abstain when supporting evidence is missing or fails validation.

## Screenshots

All captures use the demo file **`rag-test.pdf`** (fictional “Northstar Data Platform” copy). Numbers and policies in that PDF are **sample content**, not this project’s operations.

### Answer with citation

The hero image above: a Turkish question about backend stack, grounded answer with **[S1]**, model line, and structural grounding notice.

### Source behind the answer

![Expanded source S1 showing PDF excerpt, page numbers, and retrieval rank](docs/screenshots/ask-ai-source-evidence.png)

* **[S1]** opened: chunk text from `rag-test.pdf`, page list, cosine distance.*

### When the answer is not supported

![Ask AI declining to answer when citations cannot be verified](docs/screenshots/ask-ai-abstention.png)

*Question about cloud provider; the UI reports that verified sources were not returned—no fabricated answer.*

### Indexed document

![Documents tab with rag-test.pdf in Ready status](docs/screenshots/documents-indexed-pdf.png)

*After upload, process, and index—the row shows **Ready** (searchable).*

### Number from the PDF

![Answer citing a 14-day backup retention line from PDF page 3](docs/screenshots/ask-ai-numeric-fact.png)

*Single fact from page 3 with **[S1]**; questions that need several independent facts are not handled reliably.*

## How documents become answers

The LLM never sees your full library—only a small set of retrieved chunks.

```
Upload → extract → chunk → E5 embeddings → pgvector
Question → embed query → retrieve passages → Ollama (JSON)
→ validate citations / support quotes → answer + sources or abstain
```

**Citations** — The API checks that cited IDs and quoted spans match retrieved text (structural validation). That filters many invented references; it does **not** prove every statement is factually correct.

**Testing** — Phase 5D added ownership regressions, atomic delete during processing/indexing, and PostgreSQL integration coverage in CI. That is **not** a production security or SLA claim.

## Architecture & stack

| Layer | Technology |
| ----- | ------------ |
| UI | Next.js, TypeScript, Tailwind |
| Auth | Neon Auth → JWT to API |
| API | Python 3.12, FastAPI, SQLAlchemy 2, uv |
| Data | PostgreSQL 17, pgvector, Alembic |
| Embeddings | Sentence Transformers, `intfloat/multilingual-e5-small` (384-d, local CPU) |
| Answers | Ollama `qwen3:1.7b` (server-side HTTP; not fine-tuned in this repo) |

```
apps/web ──JWT/REST──► services/api ◄──► PostgreSQL (pgvector)
                           ├── local file storage
                           ├── Sentence Transformers (E5)
                           └── Ollama HTTP
```

## Tests & CI

[![CI](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml)

On every push to `main`:

1. **Frontend** — lint, typecheck, unit tests, build  
2. **Backend** — Ruff, **180+** unit tests  
3. **Backend integration** — **95+** tests on ephemeral Postgres with pgvector  

Details: [`docs/QUALITY_AUDIT.md`](docs/QUALITY_AUDIT.md)

```powershell
npm run lint
npm run typecheck
npm run test --workspace=web
npm run build
cd services\api
uv run ruff check .
uv run pytest
uv run pytest -m integration
```

## Local setup

There is **no public deployment**—run Postgres, the API, Ollama, and the Next.js dev server locally. Do not commit `.env` or `.env.local`.

**Requirements:** Node.js, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker (Postgres), [Ollama](https://ollama.com), Neon Auth variables (`NEON_AUTH_*` in the web app, `AUTH_*` in the API).

1. **Database** (repo root): `Copy-Item .env.example .env` then `docker compose up -d` (default port **5433**).  
2. **API** (`services/api`): `uv sync` → set `AUTH_*` and Ollama settings in `.env` → `uv run alembic upgrade head` → `uv run ai-knowledge-hub-api` → `ollama pull qwen3:1.7b`.  
3. **Web** (repo root): `npm install` → copy `apps/web/.env.example` to `.env.local` → `npm run dev` → open [http://localhost:3000/dashboard](http://localhost:3000/dashboard).

Development history: [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Known limitations

- Portfolio MVP only; you operate every service yourself.  
- Structural citation checks ≠ perfect answers; multi-step questions may partial-fail or abstain.  
- Process/index run inside the API worker—a crash can leave a document stuck until you fix status manually.  
- CI mocks Ollama for Ask tests; judge answer quality with a local Ollama smoke run.
