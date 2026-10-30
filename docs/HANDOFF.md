# Handoff — AI Knowledge Hub

## Repository

- **GitHub:** https://github.com/mehmetgorer/ai-knowledge-hub
- **Default branch:** `main`

## Phase 1A–1C — Summary

- Frontend (`apps/web`), FastAPI API (`services/api`), local Docker PostgreSQL 17 + pgvector.

## Phase 1D.1 / 1D.1a — Database connection & test isolation (complete)

- SQLAlchemy 2 + psycopg 3; `/health/ready`; pytest `integration` marker excluded from default runs.

## Phase 1D.2 — Alembic migrations (complete)

- **Alembic** in `services/api` (`alembic.ini`, `alembic/env.py`, `alembic/versions/`).
- `env.py` uses `get_settings().resolved_database_url` (no credentials in `alembic.ini`; safe for `%` in passwords).
- Revision **`0001_enable_vector`**: `CREATE EXTENSION IF NOT EXISTS vector`; downgrade is a no-op (extension not dropped).
- No application tables or ORM models yet.

### Alembic commands (from `services/api`)

```powershell
uv run alembic upgrade head
uv run alembic current
uv run alembic history
uv run alembic downgrade base
```

### Verification

```powershell
# Postgres (repo root)
docker compose up -d

# API (services/api)
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest                    # unit: 164 passed, 83 deselected
uv run pytest -m integration     # integration: 82 passed, 165 deselected
uv run alembic upgrade head      # idempotent on main DB

# Frontend (repo root)
npm run lint
npm run typecheck
npm run build
```

Integration tests include Alembic upgrade/downgrade on a **temporary** database (created and dropped in the test; main DB volume untouched).

## Phase 1D.2a — Alembic test safety (complete)

- Alembic integration subprocesses set explicit `DATABASE_URL` for the temporary database (overrides `.env`).
- Destructive integration tests require local `POSTGRES_HOST` and `alembic_test_*` database names; main app DB revision is checked unchanged after the test.

## Phase 2C.2 — Collections UI (complete)

- Dashboard **Collections** panel: `authClient.token()` → `GET/POST /collections` via `lib/api/client.ts` (fresh JWT per request; not stored).
- Loading, empty, error (with retry), create form with client-side name validation and duplicate-submit guard.
- **Verify Python API** retained; shared `authedApiRequest` helper.

## Phase 2C.1 — Collection API (complete)

- **`POST /collections`** — create with validated non-empty `name`; `owner_subject` from `get_current_subject` only.
- **`GET /collections`** — list current user’s collections (`created_at` descending); response includes `id`, `name`, `created_at`, `updated_at` (no cross-user access).
- SQLAlchemy session via `db_session.get_db`; no new migrations.
- Unit tests (auth + schema validation); integration tests on temporary `alembic_test_*` databases.

## Phase 2B.2a — Next.js Neon Auth (complete)

- **`@neondatabase/auth`** in `apps/web`: server (`lib/auth/server.ts`), browser client (`lib/auth/client.ts`), `GET/POST` at `/api/auth/[...path]`.
- Email/password sign-up and sign-in (`/auth/sign-up`, `/auth/sign-in`); sign-out from dashboard.
- **`/dashboard`** protected via `proxy.ts` (`auth.middleware`) plus server-side `getSession()` on the page.
- Env (local only, not in CI): `NEON_AUTH_BASE_URL`, `NEON_AUTH_COOKIE_SECRET` (≥32 chars) — see `apps/web/.env.example`. Values from Neon Console → Branch → Auth → Configuration ([Next.js API quick start](https://neon.com/docs/auth/quick-start/nextjs-api-only)).
- Missing env: no fake sessions; auth API returns `503`; protected routes redirect to sign-in; forms show a configuration message.
- Dashboard **Verify Python API** button: `authClient.token()` → `GET {NEXT_PUBLIC_API_BASE_URL}/auth/me` with `Authorization: Bearer` (token kept in memory for the request only).

## Phase 2B.2b — Next.js → FastAPI JWT (complete)

- Client-only verification on `/dashboard`; no JWT persistence in storage or React state beyond the in-flight request.
- Frontend: `NEXT_PUBLIC_API_BASE_URL` in `apps/web/.env.example` (default `http://localhost:8000` for local dev).
- API: configure `AUTH_JWKS_URL`, `AUTH_ISSUER`, and usually `AUTH_AUDIENCE` (issuer origin) per [Neon JWT guide](https://neon.com/docs/auth/guides/plugins/jwt) — see `services/api/.env.example`.
- FastAPI continues EdDSA JWKS verification; no auth bypass.

## Phase 2B.2c — JWT clock skew leeway (complete)

- **Root cause:** Neon JWT `iat` can be ~0.3s ahead of the API host UTC clock; PyJWT with `leeway=0` raised `ImmatureSignatureError` (401).
- **Fix:** `JWT_CLOCK_SKEW_LEEWAY_SECONDS = 5` passed to `jwt.decode()` in `auth/verifier.py` (EdDSA, issuer, audience, exp, iat, and nbf checks unchanged).
- Temporary `TEMP_AUTH_DIAG*` logging removed.

## Phase 2B.1a — JWKS security fix (complete)

- `PyJWKClient` uses `cache_keys=False`; bounded JWK-set cache via `lifespan` / timeout.
- Unknown `kid` → `401`; JWKS network errors → `503` (no token or exception details in responses).
- `AUTH_JWKS_URL` must be HTTPS except localhost; Neon integration: set `AUTH_JWKS_URL` from API `jwks_url`, `AUTH_ISSUER` from `base_url` origin (EdDSA tokens). See [Neon JWT guide](https://neon.com/docs/auth/guides/plugins/jwt).

## Phase 2B.1 — JWT auth verification (complete)

- **PyJWT** + **cryptography**; EdDSA-only bearer verification against **AUTH_JWKS_URL** (cached JWKS client).
- **AUTH_ISSUER** required; optional **AUTH_AUDIENCE** when tokens include `aud`.
- Fail closed if auth is not configured (`503` on protected routes).
- `GET /auth/me` returns verified `subject` only; `/health/*` remain public.
- Unit tests use local Ed25519 keys and mocked JWKS resolvers (no Neon or network in tests).

## Phase 2A — Core data model (complete)

- SQLAlchemy models: **Collection** (`owner_subject`, `name`, UUID/timestamptz) and **Document** (FK to collection, file metadata, `document_status` enum, optional SHA-256 hex, `storage_key` unique).
- `owner_subject` is for verified IdP subjects only; set from JWT via Collection API (Phase 2C.1).
- Alembic **`0002_collections_documents`** after `0001_enable_vector`; `env.py` uses `Base.metadata`.
- Unit model tests; integration tests for migrations and FK/cascade on temporary DBs only.

Apply on local Postgres: `uv run alembic upgrade head` (head = `0002_collections_documents`).

## Phase 1E — GitHub Actions CI (complete)

- Workflow `.github/workflows/ci.yml` on `push` / `pull_request` to `main`.
- Jobs: **Frontend** (Node 24, `npm ci`, lint, typecheck, build) and **Backend** (`services/api`, `uv sync --frozen`, lock check, Ruff, unit pytest).
- `permissions: contents: read`; no secrets, Docker, or integration tests in CI.
- Frontend `typecheck` runs `next typegen` before `tsc` so route types exist on clean checkouts (CI).

## Explicitly not in scope yet

- Automatic extraction on upload, chunking, embeddings, RAG/LLM.
- CI jobs for Docker / PostgreSQL integration tests.

## Phase 2D.1 — Document upload backend (complete)

- **`POST /collections/{collection_id}/documents`** — authenticated multipart upload (PDF, TXT, MD; max 10 MB default). Server-side content validation; streamed read with size cap; SHA-256; status `UPLOADED`; collection ownership via `get_owned_collection_or_404`.
- **`GET /collections/{collection_id}/documents`** — list metadata for owned collection only; responses exclude `storage_key` and filesystem paths.
- **Storage:** `LocalDocumentStorage` under configurable `DOCUMENT_STORAGE_ROOT` (default `services/api/var/document_storage`, gitignored). Generated keys `documents/{collection_id}/{uuid}`; cleanup on DB commit failure.
- Unit tests: validation, storage path safety, auth/schema; integration tests on temporary DB + temp storage directory.

### Verification (from `services/api`)

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest -m integration   # requires local Docker Postgres
```

Manual multipart upload against a running API: **not verified in automation**.

## Phase 2D.2 — Document upload UI (complete)

- Dashboard **Documents** panel (`documents-panel.tsx`): collection `<select>`, file input (PDF/TXT/MD), client-side 10 MB cap, upload via `POST /collections/{id}/documents` with `FormData`.
- Document list via `GET /collections/{id}/documents` (filename, size, status shown as **Uploaded** for `UPLOADED`, upload timestamp). List refreshes after upload and when switching collections (cancelled fetches avoid stale rows).
- `authedApiRequest` skips manual `Content-Type` for `FormData` so the browser sets the multipart boundary; JSON requests unchanged.
- Loading / empty / error + retry; duplicate upload guard; Collections panel, sign-out, and Verify Python API unchanged.
- Root `.gitignore`: `.venv/` restored; `services/api/var/` remains excluded.

Manual browser upload, collection switch, and F5 persistence: **not verified in this session** unless local web/API/Postgres were exercised end-to-end.

## Phase 2D.2a — Document list error state fix (complete)

- Document fetch state is keyed by `collectionId` on loading / ready / error (removed `loadedForCollectionId` pending heuristic that hid errors).
- `documentsViewForSelection` derives UI from the selected collection; stale responses ignored via monotonic `documentsRequestIdRef`.
- Retry and post-upload refresh unchanged in behavior.

## Phase 2D.3a — Document text extraction (complete)

- **`ai_knowledge_hub_api.documents.extraction`** — standalone service: `extract_document_text(content, filename=..., limits=...)`.
- **PDF:** pypdf page text; per-page `ExtractedPage`; `page_count` = total PDF pages; `truncated` when page or character limits apply.
- **TXT / MD:** UTF-8 decode; Markdown structure preserved (headings, lists); no rendering.
- **Normalization:** `normalize_extracted_text` trims lines, collapses inline spaces, limits blank-line runs without merging paragraphs.
- **Errors (typed, no content logged):** `UnsupportedExtractionFormatError`, `InvalidTextEncodingError`, `CorruptedDocumentError`, `EncryptedDocumentError`, `EmptyExtractionError` (image-only / no text), `ExtractionLimitExceededError` (invalid limit config).
- **Defaults:** `ExtractionLimits(max_pdf_pages=500, max_extracted_characters=512_000)`.
- **Not wired** to upload pipeline, API routes, or `Document.status` yet.

### Usage (library)

```python
from ai_knowledge_hub_api.documents.extraction import extract_document_text

result = extract_document_text(pdf_bytes, filename="report.pdf")
# result.text, result.pages, result.source_kind, result.truncated
```

### Limitations

- No OCR; scanned/image-only PDFs raise `EmptyExtractionError`.
- Extraction quality depends on pypdf text layer support.
- Character cap may truncate long documents; PDF page cap skips pages beyond the limit.

## Phase 2D.3a.1 — Extraction hardening (complete)

- PDF text budget enforced **while** reading pages (stops early; does not build full document text before truncating). Incremental cap does not guarantee a strict memory bound on a single malicious page with huge extracted text.
- Markdown uses `normalize_markdown_text` (fenced code blocks unchanged; nested list indent preserved).
- `EncryptedDocumentError` for password-protected PDFs; page-count / encryption metadata failures map to `CorruptedDocumentError`.

## Phase 2D.3b — Document chunking (complete)

- **`ai_knowledge_hub_api.documents.chunking`** — `chunk_extraction_result(extraction, config=...)` turns `ExtractionResult` into ordered `TextChunk` records (`chunk_index`, `text`, `source_kind`, `page_numbers`, `character_count`).
- Structure-aware **character** sizing (`target_characters`, `max_characters`, `overlap_characters`, `max_chunks`); sizes are **not** embedding token counts.
- PDF: page-local chunks (no cross-page mixing); plain/Markdown: paragraph, heading, sentence, then safe hard splits; Markdown preserves fenced code where possible.
- Raises `ChunkingConfigurationError` / `ChunkingLimitExceededError` on invalid settings or incomplete processing when `max_chunks` is exceeded.
- Not invoked on upload; no DB/embeddings.

## Phase 2D.3b.1 — Chunk size boundary fix (complete)

- After flush, **`overlap + next unit`** is trimmed or overlap omitted so every emitted chunk satisfies **`0 < character_count <= max_characters`** without dropping unique source text.
- **`segments.py`**: fenced-code splits enforce part lengths; tiny `max_characters`, long lines, and oversized fence openers handled with explicit fallbacks.
- Regression tests: max-sized units with overlap, overlap overflow, fenced code at small limits, source coverage, deterministic output.

## Phase 2D.3b.2 — Chunk content integrity (complete)

- Fenced Markdown splits no longer fall back to body-only hard splits; impossible `max_characters` raises **`ChunkingConfigurationError`** instead of dropping fence/language metadata.
- Overlap prefix is kept separate from the unit buffer so target/max flush never emits overlap-only duplicate chunks.
- Regression tests: fence preservation, impossible fence config, overlap-only flush scenarios.

## Phase 2D.3c.1 — Chunk persistence (complete)

- **`document_chunks`** table (Alembic `0003_document_chunks`): UUID PK, FK to `documents` ON DELETE CASCADE, `chunk_index`, `text`, `source_kind`, `page_numbers` (integer array), `character_count`, `created_at`; UNIQUE `(document_id, chunk_index)` and index on `document_id`.
- **`DocumentChunk`** SQLAlchemy model; **`replace_document_chunks`** / **`load_document_chunks`** accept `TextChunk` results; caller owns commit/rollback (delete-all-then-insert in one transaction — rollback restores prior rows).
- No new API fields or automatic processing yet in 2D.3c.1.

## Phase 2D.3c.2 — Document processing pipeline (complete)

- **`POST /collections/{collection_id}/documents/{document_id}/process`** (JWT): loads file by server `storage_key`, verifies size/SHA-256, runs extract → chunk → **`replace_document_chunks`**; response `{ id, status, chunk_count }` only (no chunk text or paths).
- **`DocumentStatus.PROCESSED`** (Alembic `0004`): UPLOADED → PROCESSING → PROCESSED on success, FAILED on error; **READY** cannot be reprocessed yet; **409** while PROCESSING or for READY.
- Short DB transactions: claim PROCESSING, then extract/chunk off-connection, then commit chunks + PROCESSED together; failures keep prior chunks and set FAILED.
- Upload does **not** auto-process.

## Phase 2D.3c.2a — Processing transaction fix (complete)

- Claim commit no longer followed by `refresh()`; document fields copied to an immutable snapshot before extract/chunk so **no SQLAlchemy transaction stays open** during storage read, PDF extraction or chunking.
- Failed claim rolls back before conflict handling; success/failure persistence behavior unchanged.

## Phase 2D.3c.3 — Document processing UI (complete)

- Dashboard **Documents** panel: per-status actions (Process / Retry / Reprocess), processing state display, per-row feedback with **chunk count from the latest process response only** (not from GET documents).
- **`processDocument`** in `apps/web/lib/api/client.ts` — authenticated POST with response validation and 401/404/409/422/network handling.

## Phase 2D.3c.3a — Processing UI race fix (complete)

- Process completion refreshes the document list **only when that collection is still selected**, avoiding `documentsRequestIdRef` invalidating another collection’s fetch.
- Synchronous **`tryAcquireProcessLock`** / **`finally` release** prevents duplicate process requests and leaked in-flight IDs.
- Stale process feedback is dropped when the user switched collections before completion.

## Phase 3A.1 — Local embedding service (complete)

- **`ai_knowledge_hub_api.embeddings`** — lazy CPU **`intfloat/multilingual-e5-small`** (384-d, L2-normalized) via Sentence Transformers.
- **`embed_document_chunks`** (`passage: ` prefix, batched) and **`embed_search_query`** (`query: ` prefix).
- Token limit **512** enforced before inference; oversized character-based chunks raise **`EmbeddingInputTooLongError`** (no silent truncation).
- First run downloads model weights from Hugging Face (~470 MB+ with PyTorch stack); plan for CPU RAM and disk.
- Optional smoke: `RUN_EMBEDDING_SMOKE=1 uv run pytest -m embedding_smoke` (not in default CI).

```python
from ai_knowledge_hub_api.embeddings import embed_document_chunks, embed_search_query

vectors = embed_document_chunks(["Chunk text…"])
query_vector = embed_search_query("Arama sorgusu")
```

## Phase 3A.2 — Chunk embedding persistence (complete)

- Alembic **`0005_document_chunk_embeddings`**: nullable **`embedding VECTOR(384)`**, **`embedding_model`**, **`embedded_at`** on **`document_chunks`** (pgvector extension from `0001`).
- **`DocumentChunk`** model updated; existing rows without embeddings remain valid.
- **`persist_document_chunk_embeddings`** / **`load_document_chunk_embeddings`**: … **`DocumentStatus.PROCESSED`** or **`INDEXING`** …
- **`embed_document_chunks`** rejects when the model returns fewer/more vectors than inputs.
- No API, no auto-embed after process, no READY transition, no vector index yet.

```python
from ai_knowledge_hub_api.embeddings.persistence import (
    ChunkEmbeddingInput,
    persist_document_chunk_embeddings,
    load_document_chunk_embeddings,
)

persist_document_chunk_embeddings(
    session,
    document_id=document.id,
    embeddings=(
        ChunkEmbeddingInput(chunk_index=0, vector=tuple(...)),
    ),
    embedding_model="intfloat/multilingual-e5-small",
)
session.commit()
stored = load_document_chunk_embeddings(session, document.id)
```

## Phase 3A.3 — On-demand document indexing (complete)

- Alembic **`0006_document_status_indexing`**: **`DocumentStatus.INDEXING`** (additive enum).
- Lifecycle: UPLOADED → PROCESSING → PROCESSED (chunks, no embeddings) → INDEXING → READY; FAILED unchanged.
- **`POST /collections/{collection_id}/documents/{document_id}/index`** (JWT): claim **PROCESSED → INDEXING**, load chunk snapshot, **`embed_document_chunks`** off-connection, **`persist_document_chunk_embeddings`**, atomically **READY**; **409** on conflict; **404** cross-user/missing; **422** on inference/persistence failure with safe messages.
- Failures restore **PROCESSED**; chunks and text preserved; no partial READY.
- Processing pipeline unchanged; **INDEXING** blocks reprocess (**409**). No auto-index on upload/process.
- Process crash may leave **INDEXING** stuck (recovery deferred).

```http
POST /collections/{collection_id}/documents/{document_id}/index
→ { "id", "status": "READY", "embedding_model", "embedded_chunk_count" }
```

### Usage (library)

```python
from ai_knowledge_hub_api.documents.extraction import extract_document_text
from ai_knowledge_hub_api.documents.chunking import chunk_extraction_result

extraction = extract_document_text(data, filename="notes.md")
chunks = chunk_extraction_result(extraction)
```

```python
from ai_knowledge_hub_api.documents.chunks import load_document_chunks, replace_document_chunks

replace_document_chunks(session, document_id=document.id, chunks=result.chunks)
session.commit()
stored = load_document_chunks(session, document.id)
```

## Phase 3A.4 — Dashboard document indexing (complete)

- **`indexDocument`** in **`apps/web/lib/api/client.ts`**: authenticated POST index; validates **READY**, **`embedding_model`**, positive **`embedded_chunk_count`**; handles **401/404/409/422**, network and invalid JSON.
- **`DocumentsPanel`**: **Process** vs **Index** actions by status; **Indexing…** in-flight; per-row feedback from latest process/index response only (not from GET documents).
- **`document-ui-actions.ts`** + **`processing-ui-guards`**: duplicate/conflict guards; collection-switch refresh/feedback rules reused from processing.
- **`formatDocumentStatus`**: includes **INDEXING**; **READY** shown as **Indexed / Ready**.
- Unit tests: **`document-ui-actions.test.ts`**, extended **`processing-ui-guards.test.ts`**.

## Phase 3B.1 — Backend semantic search (complete)

- **`POST /collections/{collection_id}/search`** (JWT): body `{ query, top_k? }` (default **5**, **1–10**); response `{ matches: [...] }` with **document_id**, **original_filename**, **chunk_index**, **text**, **source_kind**, **page_numbers**, **cosine_distance**.
- **`semantic_search_collection`** in **`ai_knowledge_hub_api.search`**: **`db.commit()`** before **`embed_search_query`**, pgvector **`cosine_distance`** in SQL, **READY** + configured **embedding_model** + non-null **embedding** only; collection **owner_subject** enforced in query; tie-break **document id**, **chunk_index**.
- Errors: **422** validation / token limit / embed failure; **404** collection; **503** DB search failure. No RAG/LLM.

```http
POST /collections/{collection_id}/search
{ "query": "Arama sorgusu", "top_k": 5 }
```

## Phase 3B.2 — Dashboard semantic search (complete)

- **`searchCollection`** in **`apps/web/lib/api/client.ts`**: POST search with **`query`** / **`top_k`** validation and strict **`matches`** parsing.
- **`DocumentsPanel`**: semantic search section (shared collection selector), top_k **3/5/10**, loading/error/empty states, passage results with metadata; **`search-ui-guards`** for stale collection/query/request races.
- Unit tests: **`lib/search/parse-search-response.test.ts`**, **`lib/search/search-ui-guards.test.ts`**, **`lib/search/search-request-lifecycle.test.ts`**; CI runs **`npm run test --workspace=web`**.

## Phase 3B.2a — Search race guard fix (complete)

- **`SearchRequestCoordinator`** + **`invalidatePendingSearch()`** on collection/query change; completion compares live query via **`searchQueryRef`**; **`endRequest`** only clears in-flight for the active request id.
- Regression: **`lib/search/search-request-lifecycle.test.ts`**.

## Phase 4A.1 — Local grounded RAG backend (complete)

- **`POST /collections/{collection_id}/ask`** (JWT): `{ "question", "top_k?" }` → `{ "answer", "sources", "model", "grounded" }`.
- Pipeline (**`ai_knowledge_hub_api.rag`**): validate → ownership → **`semantic_search_collection`** (unchanged ranking) → bounded evidence **S1…Sn** → **`db.commit()`** before Ollama → JSON **`/api/chat`** via **`httpx`** → strict citation validation.
- **Ollama** (server-side only): **`OLLAMA_BASE_URL`**, **`OLLAMA_MODEL`** (default **`qwen3:1.7b`**), **`OLLAMA_REQUEST_TIMEOUT_SECONDS`**, **`RAG_MAX_EVIDENCE_*`**, **`RAG_MAX_OUTPUT_TOKENS`**. No paid/cloud inference; prompts and document text are not logged.
- **`grounded: true`** only when **`evidence_sufficient: true`**, valid **Sx** citations present in the answer, and structural checks pass; invalid combinations → **422**; abstention → **`grounded: false`** (empty sources); no chunks → safe message without LLM.
- Errors: **503** Ollama offline/timeout/missing model; **422** grounding/validation; retrieval errors same as search.
- Tests: **`test_ask.py`**, **`test_rag_*.py`**, **`test_ask_integration.py`** (mocked Ollama; no model download in CI).

```http
POST /collections/{collection_id}/ask
{ "question": "What does SQL JOIN do?", "top_k": 5 }
```

**Local Ollama:** install [Ollama](https://ollama.com), run `ollama serve` (default **11434**), pull model e.g. `ollama pull qwen3:1.7b`. Real answer quality/citation behavior is **not verified in CI** (mocked LLM only).

## Phase 4A.2 — Dashboard Ask AI (complete)

- **`askCollection`** in **`apps/web/lib/api/client.ts`**: POST **`/collections/{id}/ask`**, strict **`parseAskResponse`**, handles **401/404/422/503**, network and malformed JSON.
- **`DocumentsPanel`**: violet **Ask AI** block (shared collection selector), question textarea, top_k **3/5/10**, generating/error/retry, answer with inline **[Sx]** markers, model + grounding label (structural validation — not fact-checked), expandable sources with distance as rank only.
- **`SearchRequestCoordinator`** (separate ref) + **`ask-ui-guards`** for stale collection/question races; no localStorage persistence.
- Unit tests: **`lib/ask/*.test.ts`**; CI **`npm run test --workspace=web`**.

## Phase 4A.3 — RAG reliability (complete)

- **Prompts:** answers limited to **explicitly stated** passage text; no extrapolated formulas/terms; required JSON field **`evidence_sufficient`** (structural — not factual verification).
- **Validation:** `evidence_sufficient: false` rejects any citations; `true` requires valid **Sx** markers; prompt states citation checks do **not** guarantee factual correctness.
- **Ollama:** **`OLLAMA_TEMPERATURE=0`**, **`OLLAMA_THINK_ENABLED=false`** (Qwen3 thinking off when supported), JSON **`format`**, existing token/timeout limits.
- **Retrieval threshold:** optional **`RAG_WEAK_RETRIEVAL_BEST_DISTANCE_ABOVE`** (default **disabled**); calibration tests in **`test_rag_relevance_calibration.py`** show aggressive cutoffs harm cross-language matches — not enabled in production defaults.
- Tests: **`test_rag_reliability.py`**, **`test_rag_relevance_calibration.py`**, extended **`test_rag_validation.py`**, **`test_ask_integration.py`**.

## Phase 4A.3a — Ollama grounded answer repair (complete)

- **Root fix:** real Qwen3 often returned **`cited_source_ids`** without matching inline **`[Sx]`** markers → **`missing_inline_citation`** (422). Validation unchanged; one bounded **repair** attempt with formatting-only hints.
- **Ollama:** JSON **`format`** uses **`GROUNDED_ANSWER_JSON_SCHEMA`** (`answer`, **`evidence_sufficient`**, **`cited_source_ids`**); still **`temperature=0`**, **`think: false`**.
- **Pipeline:** **`complete_and_validate_grounded_answer`** (`rag/generation.py`) → parse (`parse_completion.py`) → validate with codes (`validation_codes.py`) → optional repair (`repair.py`). Server logs **`code=`** and attempt only (no questions, passages, prompts, or answers).
- **`RagGroundingError.code`:** safe category for logs; API still returns generic **422** detail.
- Tests: **`test_rag_generation.py`**, updated **`test_rag_validation.py`**, **`test_rag_reliability.py`** (schema in request body). CI uses mocked Ollama only — **live qwen3:1.7b not verified in CI** (manual re-test recommended after deploy).

## Phase 4A.3b — Fail-closed RAG grounding (complete)

- **Deterministic abstention:** whenever the pipeline decides the answer is not grounded (`evidence_sufficient=false`, no/weak evidence, or post-validation fail-closed), the API returns **`build_insufficient_sources_answer(question)`** — never the model’s `answer` text. `grounded=false`, `sources=[]`; response shape unchanged.
- **Verbatim support quotes:** JSON schema adds required **`support_quotes`** (`{source_id, quote}`); each quote must be a substring of the retrieved chunk (≥8 chars). Invalid quotes → one repair attempt, then fail-closed abstention with logged codes (`quote_not_in_source`, etc.).
- **Conservative heuristics (not semantic verification):** when `evidence_sufficient=true`, reject (then fail-closed after repair) if cited passages do not contain **years (1000–2099)**, **3+ digit numbers**, or **formula-like claims** when the question asks for a formula — codes `unsupported_date`, `unsupported_numeric`, `unsupported_formula`. Ordinary paraphrases without those signals still pass if citations and quotes validate.
- **Limitation:** extra prose beyond quoted passages is **not** fully detected; quote + high-risk checks reduce hallucinated formulas/dates/numbers but do not eliminate all unsupported detail.
- Tests: **`test_rag_fail_closed.py`**, extended **`test_ask_integration.py`**, updated generation/validation/reliability tests. CI: mocked Ollama only.

### Manual evaluation (real `qwen3:1.7b`, local Ollama)

1. `docker compose up -d`, `uv run alembic upgrade head`, API + web with `.env` configured; `ollama serve` + `ollama pull qwen3:1.7b`.
2. Index fixtures containing `database.txt`, `machine-learning.txt` (no Titanic date, no chain-rule formula in ML chunk).
3. Ask via dashboard or `POST /collections/{id}/ask`:
   - **JOIN (TR):** expect `grounded=true`, inline `[S1]`, sources populated; answer should track cited passage (minor paraphrase OK).
   - **Chain rule formula (TR):** expect safe Turkish abstention — **no fabricated formula** in `answer`.
   - **Titanic date (TR):** expect safe abstention — **no 1912/date** in `answer`.
4. Inspect API logs for `code=` only (no question/passage/answer bodies).

## Recommended next steps

1. Optional manual re-test of Qwen3 after prompt/`evidence_sufficient` changes.
2. Optional scheduled or manual workflow for `pytest -m integration` with Docker.
3. Document production `DATABASE_URL` for managed Postgres.

## Notes

- Frontend unchanged in Phase 1D.2.
- Never log or return database credentials from the API or Alembic.
