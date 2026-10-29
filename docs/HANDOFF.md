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
uv run pytest                    # unit: 73 passed, 11 deselected
uv run pytest -m integration     # integration: 11 passed, 73 deselected
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
- **Errors (typed, no content logged):** `UnsupportedExtractionFormatError`, `InvalidTextEncodingError`, `CorruptedDocumentError`, `EmptyExtractionError` (image-only / no text), `ExtractionLimitExceededError` (invalid limit config).
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

## Recommended next steps

1. Document parsing / chunking pipeline after upload.
2. Optional scheduled or manual workflow for `pytest -m integration` with Docker.
3. Document production `DATABASE_URL` for managed Postgres.

## Notes

- Frontend unchanged in Phase 1D.2.
- Never log or return database credentials from the API or Alembic.
