# AI Knowledge Hub (Yapay Zekâ Bilgi Merkezi)

**English** | [Türkçe](README.tr.md)

**Ask questions about your documents and get AI-generated answers with source references.**

*Belgelerinize soru sorun; yapay zekâ yanıtları kaynak referanslarıyla birlikte gelsin.*

AI Knowledge Hub is a full-stack app for organizing files, searching their meaning, and asking questions with **locally running** models. It is a **portfolio demonstration**: there is **no public live demo URL**—you run the web UI, API, PostgreSQL, embeddings, and Ollama on your machine.

Screenshots below use the synthetic evaluation PDF **`rag-test.pdf`** (fictional “Northstar Data Platform” text). Those facts are **not** claims about this repository’s production infrastructure or business policies.

![Ask AI giving a grounded answer in Turkish with a citation to rag-test.pdf](docs/screenshots/ask-ai-grounded-answer.png)

## What it does

- **Private collections** — Sign in; each user sees only their own collections and documents.
- **Upload** — PDF, TXT, or Markdown (size and type validated).
- **Process & index** — Extract text, chunk it, embed with **multilingual E5**, store vectors in **PostgreSQL + pgvector**.
- **Semantic search** — Rank passages by meaning (cosine distance), scoped to your collection. *(Not shown in screenshots; same retrieval engine powers Ask AI.)*
- **Ask AI** — Retrieve passages, call **Ollama (qwen3:1.7b)**, validate citations and support quotes, then show an answer—or **abstain** when evidence is insufficient.

## Screenshots (demonstration data)

### Source evidence

![Expanded PDF source passage with page metadata and retrieval rank](docs/screenshots/ask-ai-source-evidence.png)

*Source **[S1]** expanded: chunk text, pages, cosine distance.*

### Safe abstention

![Safe abstention when the document does not support the question](docs/screenshots/ask-ai-abstention.png)

*No verified passages — the app refuses to invent an answer.*

### Document ready for search

![Indexed rag-test.pdf in the Documents tab](docs/screenshots/documents-indexed-pdf.png)

*Upload → process → index → **Ready**.*

### Grounded numeric fact

![Grounded numeric fact with citation to PDF page 3](docs/screenshots/ask-ai-numeric-fact.png)

*Single-fact retrieval; multi-part questions are not consistently handled.*

## How documents become answers

The model never receives your entire library—only a small set of retrieved chunks.

```
Upload → extract text → chunk → E5 embeddings → pgvector
Question → embed query → retrieve top passages → Ollama JSON answer
→ validate citations / quotes → show sources or abstain
```

**Citations** — Source IDs and support quotes must match retrieved text (**structural** validation). That catches many unsupported or invented references; it is **not** full semantic fact-checking.

**Reliability** — Phase 5D audit: ownership tests, atomic delete during processing/indexing, PostgreSQL integration tests in CI. That does **not** mean production-grade security or SLA guarantees.

## Architecture & stack

| Layer | Technology |
| ----- | ------------ |
| UI | Next.js, TypeScript, Tailwind |
| Auth | Neon Auth → JWT to API |
| API | FastAPI, SQLAlchemy 2, uv |
| Data | PostgreSQL 17, pgvector, Alembic |
| Embeddings | `intfloat/multilingual-e5-small` (local CPU) |
| Answers | Ollama `qwen3:1.7b` (server-side only) |

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

Requirements: Node.js, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker (Postgres), [Ollama](https://ollama.com), Neon Auth env vars. Never commit `.env` / `.env.local`.

1. **Database** (repo root): `Copy-Item .env.example .env` → `docker compose up -d` (port **5433** by default).  
2. **API** (`services/api`): `uv sync` → configure `AUTH_*` and Ollama in `.env` → `uv run alembic upgrade head` → `uv run ai-knowledge-hub-api` → `ollama pull qwen3:1.7b`.  
3. **Web**: `npm install` → `apps/web/.env.local` from `.env.example` → `npm run dev` → [http://localhost:3000/dashboard](http://localhost:3000/dashboard).

Full phase notes: [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Known limitations

- Local-only MVP; no hosted deployment in this repo.  
- Citation validation ≠ perfect answers; complex multi-hop questions may fail partially or abstain.  
- Processing/indexing runs in the API process; a crash can leave a document stuck until manual fix.  
- CI mocks Ollama for Ask tests; real answer quality requires local Ollama smoke tests.
