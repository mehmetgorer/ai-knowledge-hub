# Quality Audit — Phase 5D (2026-03-30)

Audit scope: **reliability, security, reproducibility** of the current RAG MVP. No feature redesign. Evidence from **source review**, **local test runs**, and **targeted regression tests** added in this phase.

## Architecture summary

| Layer | Responsibility | Notes |
| ----- | -------------- | ----- |
| `apps/web` | Neon Auth (JWT in memory per request), dashboard UX | No secrets in repo; API calls via Bearer token |
| `services/api` | FastAPI, ownership checks on collections/documents, document pipeline, pgvector search, Ollama RAG | JWT verified via JWKS (Ed25519), `sub` → `owner_subject` |
| PostgreSQL + pgvector | Collections, documents, chunks, embeddings | Integration tests use ephemeral `alembic_test_*` DBs only |
| Local disk | `LocalDocumentStorage` under configurable root | Path traversal blocked; delete-after-DB-commit with orphan-file warning |

## Security and data isolation

### Verified mechanisms

- **JWT:** `verify_access_token` — algorithm allow-list, issuer, exp, optional audience, JWKS resolver with cache/TTL (`auth/verifier.py`, `auth/dependencies.py`). Unit tests: missing/invalid/expired/wrong issuer/alg/subject (`tests/test_auth.py`).
- **Collection ownership:** `get_owned_collection_or_404` — list/create/search/ask/upload scoped by `owner_subject`.
- **Document ownership:** `get_owned_document_or_404` — document must belong to collection **and** collection to user; wrong collection ID → **404** (not 403), reducing ID oracle leakage.
- **Search / Ask:** `semantic_search_collection` and `ask_collection_question` join `Collection.owner_subject`; only **READY** chunks with embeddings participate in retrieval.
- **Upload:** Size limit streaming read, MIME/extension validation, storage key generation, hash optional; `LocalDocumentStorage.resolve_key_path` rejects `..` and absolute keys.
- **RAG grounding:** Citation validation, invented source IDs, malformed JSON, prompt-injection passages in evidence — covered by `test_rag_*` and `test_ask_integration.py` (fail-closed / abstention paths).

### Regression tests added (Phase 5D)

- `tests/test_security_isolation_integration.py` — cross-user list **404**; same-user **wrong collection** for process/index/delete **404** with row preserved.

### Limits (not proven “secure everywhere”)

- Citation validation checks **structural grounding** against retrieved passages, not full semantic fact-checking.
- Rate limiting, WAF, and production secret rotation are **out of scope** for this MVP.
- Dependency CVE scan: **`uv`/`pip audit` not run in CI** (no audit tool in current uv workflow); manual review of lockfile deferred to ops.

## Document lifecycle

### Processing / indexing (existing + verified)

- **Atomic claims:** `UPDATE … WHERE status IN (eligible)` for PROCESSING and INDEXING (`processing/service.py`, `indexing/service.py`). Concurrent duplicate process → **409** (integration test with slow extract).
- **Failure recovery:** Processing failure → **FAILED** (reprocess allowed). Index failure → **PROCESSED** restored, chunks kept (integration tests).
- **Interrupted work:** If the API process dies **after** status commit to PROCESSING/INDEXING, the row can remain stuck until manual intervention — **no watchdog** (P2, documented).

### Deletion

| Risk | Finding | Priority | Action |
| ---- | ------- | -------- | ------ |
| Delete vs process race | Pre-5D: ORM status check then `db.delete()` could delete a row that had moved to PROCESSING if handler held stale object | **P1** | **Fixed:** conditional `DELETE … WHERE status NOT IN (PROCESSING, INDEXING) RETURNING storage_key` (`deletion.py`) |
| Delete vs index | INDEXING blocked same as PROCESSING | — | Already rejected; integration test `test_delete_rejects_indexing_document` added |
| Orphan files | DB commit then storage delete; storage failure logs warning | P2 | Documented in HANDOFF Phase 5B; no reconciler |
| Stuck PROCESSING/INDEXING | No auto-reset after crash | P2 | Document only |

Tests: `test_document_deletion.py` (unit), `test_document_deletion_integration.py` (atomic stale view, indexing block), existing processing/indexing integration suite.

## PDF and embedding robustness

Existing integration coverage (not re-run with new binaries in CI):

- Blank / encrypted PDF → **FAILED**, no chunks (`test_document_processing_integration.py`).
- Missing storage → **FAILED**.
- Reprocess after failure preserves prior chunks when applicable.
- Search/index: token limit → **422**; embedding dimension checks in unit tests.

**Not measured in this audit:** CPU/memory profiling on large PDFs; real 10MB+ uploads in CI (bounded by `document_max_upload_bytes` in settings).

## RAG and retrieval evaluation

### Pipeline tests (existing)

- End-to-end Ask with mocked Ollama: grounded answers, abstention, bad citations, deleted doc exclusion from search, cross-user search **404**.

### Synthetic metrics (Phase 5D)

- `tests/test_rag_retrieval_eval.py` — orthogonal basis vectors in PostgreSQL; mocked query embedding aligned to chunk index **2**.
- **Measured (single scenario, deterministic):** Recall@3 = **1.0**, Recall@5 = **1.0**, MRR = **1.0** (target rank 1).
- **Not measured:** Turkish/English real-model benchmarks, latency SLAs, or multi-document overlap — requires local Ollama + `qwen3:1.7b` manual run.

## Test infrastructure and CI

### Local runs (2026-03-30, Windows, Docker Postgres)

| Suite | Command | Result |
| ----- | ------- | ------ |
| Backend unit | `uv run pytest` | **180 passed**, 96 deselected |
| Backend integration | `uv run pytest -m integration` | **95 passed**, 181 deselected (~152s) |
| Frontend | lint, typecheck, test, build | **41** Node tests pass; build OK |

### CI changes (Phase 5D)

- New job **`Backend integration (PostgreSQL)`** — `pgvector/pg17` service on port **5433**, runs `pytest -m integration`.
- Unit job unchanged on GitHub-hosted runners without requiring developer DB.

Integration safety: `assert_local_postgres_host`, `alembic_test_*` database names only, main DB revision unchanged after tests (`tests/alembic_test_support.py`).

## API and code quality (spot review)

- Request bodies bounded via Pydantic (`CollectionSearchRequest`, upload limits).
- DB sessions per request (`get_db`); long work (extract, embed) committed outside long transactions where designed.
- Errors: generic auth messages (no token leakage); 503 on delete commit failure with row retained.
- Frontend: collection switch invalidates stale search/ask/process UI state (unit tests in `apps/web`).

## Findings register

| ID | Priority | Summary | Evidence | Fix / disposition |
| -- | -------- | ------- | -------- | ----------------- |
| DEL-01 | P1 | Stale ORM could bypass PROCESSING delete guard | Code review + `test_atomic_delete_rejects_stale_uploaded_view_when_processing` | Atomic SQL delete |
| SEC-01 | P2 | Cross-collection ID manipulation | New integration tests | No code change required (404) |
| LIFE-01 | P2 | Stuck PROCESSING/INDEXING after hard kill | Design review | Document; manual status fix or re-upload |
| LIFE-02 | P2 | Orphan disk files after DB delete | HANDOFF 5B | Document |
| RAG-01 | P2 | No automated real-LLM eval in CI | By design (Ollama) | Synthetic retrieval metric only |
| OPS-01 | P2 | No dependency CVE gate in CI | Tooling gap | Track in production hardening |
| DOC-01 | P2 | Root README CI blurb omits integration job | README line 12 | Note for doc phase |

## Portfolio MVP vs public production

| Concern | Portfolio MVP (demonstrable today) | Public production |
| ------- | ----------------------------------- | ----------------- |
| Auth + isolation | JWT + ownership tests + new isolation regressions | MFA, audit logs, rate limits |
| Data safety | Ephemeral CI DB; local dev volume | Managed Postgres, backups, encryption at rest |
| RAG correctness | Grounding/citation guards + synthetic Recall@k | Human eval, monitoring, model versioning |
| Operations | Docker Compose dev | HA API, object storage, stuck-job reconciler, CVE pipeline |

## Reproducible local verification

```powershell
# Repo root — Postgres
docker compose up -d

# Backend (services/api)
uv run ruff check .
uv run ruff format --check .
uv run pytest                    # unit
uv run pytest -m integration     # ~95 tests, needs local Postgres

# Frontend (repo root)
npm run lint
npm run typecheck
npm run test --workspace=web
npm run build
```

Optional real-model smoke: index a small TXT/PDF, search, ask with Ollama running and `qwen3:1.7b` pulled locally.
