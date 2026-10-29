"""Integration tests for on-demand document indexing."""

import math
import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.auth.dependencies import (
    get_current_subject,
    get_jwks_resolver,
)
from ai_knowledge_hub_api.auth.jwks import StaticJwksResolver
from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.database import dispose_engine
from ai_knowledge_hub_api.documents.indexing import index_document
from ai_knowledge_hub_api.documents.processing import process_document
from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import EmbeddingInputTooLongError
from ai_knowledge_hub_api.embeddings.persistence import load_document_chunk_embeddings
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from ai_knowledge_hub_api.models import (
    Collection,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from ai_knowledge_hub_api.storage.dependencies import document_storage_for_settings
from tests.alembic_test_support import (
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
    read_alembic_revision,
    run_alembic,
)
from tests.auth_keys import (
    TEST_ISSUER,
    TEST_JWKS_URL,
    Ed25519KeyPair,
    generate_ed25519_key_pair,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"
_CONFIG = EmbeddingConfig()


def _mock_embed(texts, config: EmbeddingConfig) -> list[list[float]]:
    del config
    scale = 1.0 / math.sqrt(_CONFIG.expected_dimensions)
    return [[scale] * _CONFIG.expected_dimensions for _ in texts]


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("AUTH_AUDIENCE", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def key_pair() -> Ed25519KeyPair:
    return generate_ed25519_key_pair()


@pytest.fixture
def migrated_indexing_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}index_{uuid.uuid4().hex[:8]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

    storage_root = tmp_path / "document_storage"
    monkeypatch.setenv("DOCUMENT_STORAGE_ROOT", str(storage_root))

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        result = run_alembic("upgrade", "head", database_url=temp_url)
        assert result.returncode == 0, result.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        monkeypatch.setenv("DATABASE_URL", temp_url)
        get_settings.cache_clear()
        dispose_engine()
        yield temp_url
    finally:
        get_settings.cache_clear()
        dispose_engine()
        assert_safe_temporary_database_name(db_name, main_database)
        with _admin_engine(settings).connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :dbname AND pid <> pg_backend_pid()
                    """
                ),
                {"dbname": db_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))

        assert read_alembic_revision(main_url) == main_revision_before


def _client_for_subject(
    key_pair: Ed25519KeyPair,
    subject: str,
) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_jwks_resolver] = lambda: StaticJwksResolver(
        {key_pair.kid: key_pair.public_key}
    )
    app.dependency_overrides[get_current_subject] = lambda: subject
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _create_collection(client: httpx.AsyncClient, name: str = "Docs") -> str:
    response = await client.post("/collections", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


async def _upload(
    client: httpx.AsyncClient,
    collection_id: str,
    filename: str,
    content: bytes,
) -> dict:
    response = await client.post(
        f"/collections/{collection_id}/documents",
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


async def _process(client: httpx.AsyncClient, collection_id: str, document_id: str):
    return await client.post(
        f"/collections/{collection_id}/documents/{document_id}/process",
    )


async def _index(client: httpx.AsyncClient, collection_id: str, document_id: str):
    return await client.post(
        f"/collections/{collection_id}/documents/{document_id}/index",
    )


async def _prepare_processed_document(
    client: httpx.AsyncClient,
    content: bytes = b"First paragraph.\n\nSecond paragraph for indexing.",
) -> tuple[str, str]:
    collection_id = await _create_collection(client)
    uploaded = await _upload(client, collection_id, "notes.txt", content)
    process_response = await _process(client, collection_id, uploaded["id"])
    assert process_response.status_code == 200
    return collection_id, uploaded["id"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_index_processed_document_reaches_ready(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    with patch(
        "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
        side_effect=_mock_embed,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            collection_id, document_id = await _prepare_processed_document(client)
            response = await _index(client, collection_id, document_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["embedding_model"] == _CONFIG.model_name
    assert payload["embedded_chunk_count"] >= 1

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        assert document.status == DocumentStatus.READY
        stored = load_document_chunk_embeddings(session, uuid.UUID(document_id))
        assert len(stored) == payload["embedded_chunk_count"]
        for item in stored:
            assert len(item.vector) == 384
            assert item.embedding_model == _CONFIG.model_name
            norm = math.sqrt(sum(v * v for v in item.vector))
            assert math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4)


@pytest.mark.integration
@pytest.mark.anyio
async def test_index_preserves_chunk_order_and_text(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    with patch(
        "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
        side_effect=_mock_embed,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            collection_id, document_id = await _prepare_processed_document(client)
            assert (await _index(client, collection_id, document_id)).status_code == 200

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
            .order_by(DocumentChunk.chunk_index)
        ).all()
        stored = load_document_chunk_embeddings(session, uuid.UUID(document_id))
    assert [c.chunk_index for c in chunks] == [s.chunk_index for s in stored]
    assert all(c.text.strip() for c in chunks)


@pytest.mark.integration
@pytest.mark.anyio
async def test_concurrent_index_requests_return_conflict(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id, document_id = await _prepare_processed_document(client)

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        document.status = DocumentStatus.INDEXING
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        response = await _index(client, collection_id, document_id)
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.anyio
async def test_cross_user_index_is_not_found(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    with patch(
        "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
        side_effect=_mock_embed,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            collection_id, document_id = await _prepare_processed_document(client)

        async with _client_for_subject(key_pair, "owner-b") as client:
            response = await _index(client, collection_id, document_id)

    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSING,
        DocumentStatus.FAILED,
        DocumentStatus.READY,
        DocumentStatus.INDEXING,
    ],
)
async def test_index_invalid_status_returns_conflict(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
    status: DocumentStatus,
) -> None:
    del migrated_indexing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(client, collection_id, "x.txt", b"hello")

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        document.status = status
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        response = await _index(client, collection_id, uploaded["id"])
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.anyio
async def test_embedding_failure_restores_processed_without_vectors(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    def fail_embed(_texts, _config):
        raise EmbeddingInputTooLongError(
            "too long",
            token_count=999,
            max_tokens=512,
            character_count=1000,
            input_kind="passage[0]",
        )

    with patch(
        "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
        side_effect=fail_embed,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            collection_id, document_id = await _prepare_processed_document(client)
            response = await _index(client, collection_id, document_id)

    assert response.status_code == 422

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        assert document.status == DocumentStatus.PROCESSED
        stored = load_document_chunk_embeddings(session, uuid.UUID(document_id))
        assert stored == ()


@pytest.mark.integration
@pytest.mark.anyio
async def test_persistence_failure_restores_processed(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    with (
        patch(
            "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
            side_effect=_mock_embed,
        ),
        patch(
            "ai_knowledge_hub_api.documents.indexing.service.persist_document_chunk_embeddings",
            side_effect=RuntimeError("simulated persistence failure"),
        ),
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            collection_id, document_id = await _prepare_processed_document(client)
            response = await _index(client, collection_id, document_id)

    assert response.status_code == 422

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        assert document.status == DocumentStatus.PROCESSED
        assert load_document_chunk_embeddings(session, uuid.UUID(document_id)) == ()


@pytest.mark.integration
def test_embedding_runs_without_active_db_transaction(
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database
    settings = get_settings()
    engine = create_engine(settings.resolved_database_url)
    storage = document_storage_for_settings(settings)
    content = b"Index without open transaction."

    txn_during_embed: list[bool] = []
    indexing_session: Session | None = None

    def track_embed(texts, config):
        assert indexing_session is not None
        txn_during_embed.append(indexing_session.in_transaction())
        return _mock_embed(texts, config)

    with patch(
        "ai_knowledge_hub_api.documents.indexing.service.embed_document_chunks",
        side_effect=track_embed,
    ):
        with Session(engine) as session:
            indexing_session = session
            collection = Collection(owner_subject="provider|idx-txn", name="Idx")
            session.add(collection)
            session.flush()
            document = Document(
                collection_id=collection.id,
                original_filename="notes.txt",
                mime_type="text/plain",
                size_bytes=len(content),
                storage_key=f"documents/{collection.id}/{uuid.uuid4()}",
                status=DocumentStatus.UPLOADED,
            )
            session.add(document)
            session.commit()
            storage.write(document.storage_key, content)
            process_document(session, document=document, storage=storage)
            session.refresh(document)
            index_document(session, document=document)

    assert txn_during_embed
    assert all(flag is False for flag in txn_during_embed)


@pytest.mark.integration
@pytest.mark.anyio
async def test_indexing_document_cannot_be_reprocessed(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_indexing_database: str,
) -> None:
    del migrated_indexing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id, document_id = await _prepare_processed_document(client)

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        document.status = DocumentStatus.INDEXING
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        response = await _process(client, collection_id, document_id)
    assert response.status_code == 409
