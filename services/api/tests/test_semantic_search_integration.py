"""Integration tests for collection semantic search."""

import math
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.auth.dependencies import (
    get_current_subject,
    get_jwks_resolver,
)
from ai_knowledge_hub_api.auth.jwks import StaticJwksResolver
from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.database import dispose_engine
from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import EmbeddingInputTooLongError
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from ai_knowledge_hub_api.models import (
    Collection,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from ai_knowledge_hub_api.search.service import semantic_search_collection
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
_MODEL = _CONFIG.model_name
_DIM = _CONFIG.expected_dimensions


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


def _basis_vector(index: int, *, dimensions: int = _DIM) -> list[float]:
    vector = [0.0] * dimensions
    vector[index] = 1.0
    return vector


def _mock_embed_query(
    text: str, *, config: EmbeddingConfig | None = None
) -> list[float]:
    del text, config
    return _basis_vector(0)


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
def migrated_search_database(monkeypatch: pytest.MonkeyPatch) -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}search_{uuid.uuid4().hex[:8]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

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


def _add_ready_chunk(
    session: Session,
    *,
    collection: Collection,
    filename: str,
    chunk_index: int,
    text: str,
    embedding: list[float],
    embedding_model: str = _MODEL,
    page_numbers: list[int] | None = None,
) -> Document:
    document = Document(
        collection_id=collection.id,
        original_filename=filename,
        mime_type="text/plain",
        size_bytes=128,
        storage_key=f"storage/{uuid.uuid4()}",
        status=DocumentStatus.READY,
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentChunk(
            document_id=document.id,
            chunk_index=chunk_index,
            text=text,
            source_kind="text",
            page_numbers=page_numbers or [chunk_index + 1],
            character_count=len(text),
            embedding=embedding,
            embedding_model=embedding_model,
            embedded_at=datetime.now(UTC),
        )
    )
    session.flush()
    return document


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_ranks_by_cosine_distance(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Search")
        session.add(collection)
        session.flush()
        _add_ready_chunk(
            session,
            collection=collection,
            filename="near.txt",
            chunk_index=0,
            text="Closest chunk.",
            embedding=_basis_vector(0),
        )
        _add_ready_chunk(
            session,
            collection=collection,
            filename="far.txt",
            chunk_index=0,
            text="Farther chunk.",
            embedding=_basis_vector(1),
        )
        session.commit()
        collection_id = str(collection.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "test query", "top_k": 5},
            )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 2
    assert matches[0]["original_filename"] == "near.txt"
    assert matches[0]["cosine_distance"] <= matches[1]["cosine_distance"]
    assert matches[0]["cosine_distance"] == pytest.approx(0.0, abs=1e-5)


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_respects_top_k(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="TopK")
        session.add(collection)
        session.flush()
        for index in range(4):
            _add_ready_chunk(
                session,
                collection=collection,
                filename=f"doc-{index}.txt",
                chunk_index=0,
                text=f"Chunk {index}",
                embedding=_basis_vector(index),
            )
        session.commit()
        collection_id = str(collection.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "limit", "top_k": 2},
            )

    assert response.status_code == 200
    assert len(response.json()["matches"]) == 2


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_isolates_collections_and_users(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        col_a = Collection(owner_subject="owner-a", name="A")
        col_b = Collection(owner_subject="owner-b", name="B")
        session.add_all([col_a, col_b])
        session.flush()
        _add_ready_chunk(
            session,
            collection=col_a,
            filename="secret-a.txt",
            chunk_index=0,
            text="Owner A only",
            embedding=_basis_vector(0),
        )
        _add_ready_chunk(
            session,
            collection=col_b,
            filename="secret-b.txt",
            chunk_index=0,
            text="Owner B only",
            embedding=_basis_vector(0),
        )
        session.commit()
        id_a, id_b = str(col_a.id), str(col_b.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            ok = await client.post(
                f"/collections/{id_a}/search",
                json={"query": "find"},
            )
            cross = await client.post(
                f"/collections/{id_b}/search",
                json={"query": "find"},
            )

    assert ok.status_code == 200
    assert len(ok.json()["matches"]) == 1
    assert ok.json()["matches"][0]["text"] == "Owner A only"
    assert cross.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_excludes_non_ready_and_bad_embeddings(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Filter")
        session.add(collection)
        session.flush()
        ready = Document(
            collection_id=collection.id,
            original_filename="ready.txt",
            mime_type="text/plain",
            size_bytes=1,
            storage_key=f"k/{uuid.uuid4()}",
            status=DocumentStatus.READY,
        )
        processed = Document(
            collection_id=collection.id,
            original_filename="processed.txt",
            mime_type="text/plain",
            size_bytes=1,
            storage_key=f"k/{uuid.uuid4()}",
            status=DocumentStatus.PROCESSED,
        )
        session.add_all([ready, processed])
        session.flush()
        session.add(
            DocumentChunk(
                document_id=ready.id,
                chunk_index=0,
                text="Included",
                source_kind="text",
                page_numbers=[1],
                character_count=8,
                embedding=_basis_vector(0),
                embedding_model=_MODEL,
                embedded_at=datetime.now(UTC),
            )
        )
        session.add(
            DocumentChunk(
                document_id=processed.id,
                chunk_index=0,
                text="Processed only",
                source_kind="text",
                page_numbers=[1],
                character_count=14,
                embedding=_basis_vector(1),
                embedding_model=_MODEL,
                embedded_at=datetime.now(UTC),
            )
        )
        session.add(
            DocumentChunk(
                document_id=ready.id,
                chunk_index=1,
                text="Wrong model",
                source_kind="text",
                page_numbers=[2],
                character_count=11,
                embedding=_basis_vector(2),
                embedding_model="other/model",
                embedded_at=datetime.now(UTC),
            )
        )
        session.commit()
        collection_id = str(collection.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "q"},
            )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["text"] == "Included"


@pytest.mark.integration
@pytest.mark.anyio
async def test_empty_collection_returns_no_matches(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Empty")
        session.add(collection)
        session.commit()
        collection_id = str(collection.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "anything"},
            )

    assert response.status_code == 200
    assert response.json()["matches"] == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_invalid_query_and_token_limit_return_422(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Errors")
        session.add(collection)
        session.commit()
        collection_id = str(collection.id)

    async with _client_for_subject(key_pair, "owner-a") as client:
        empty = await client.post(
            f"/collections/{collection_id}/search",
            json={"query": "   "},
        )

    assert empty.status_code == 422

    def fail_embed(_text, *, config=None):
        del config
        raise EmbeddingInputTooLongError(
            "too long",
            token_count=999,
            max_tokens=512,
            character_count=1000,
            input_kind="query",
        )

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=fail_embed,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "valid but too long for mock"},
            )

    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_returns_source_metadata(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Meta")
        session.add(collection)
        session.flush()
        _add_ready_chunk(
            session,
            collection=collection,
            filename="report.pdf",
            chunk_index=3,
            text="Page metadata chunk",
            embedding=_basis_vector(0),
            page_numbers=[2, 3],
        )
        session.commit()
        collection_id = str(collection.id)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            response = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "meta"},
            )

    match = response.json()["matches"][0]
    assert match["original_filename"] == "report.pdf"
    assert match["chunk_index"] == 3
    assert match["page_numbers"] == [2, 3]
    assert match["source_kind"] == "text"


@pytest.mark.integration
def test_search_embedding_runs_without_active_db_transaction(
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)
    txn_flags: list[bool] = []
    search_session: Session | None = None

    def track_embed(_text, *, config=None):
        del _text, config
        assert search_session is not None
        txn_flags.append(search_session.in_transaction())
        return _basis_vector(0)

    with Session(engine) as session:
        search_session = session
        collection = Collection(owner_subject="owner-a", name="Txn")
        session.add(collection)
        session.flush()
        _add_ready_chunk(
            session,
            collection=collection,
            filename="a.txt",
            chunk_index=0,
            text="Hello",
            embedding=_basis_vector(0),
        )
        session.commit()
        with patch(
            "ai_knowledge_hub_api.search.service.embed_search_query",
            side_effect=track_embed,
        ):
            matches = semantic_search_collection(
                session,
                collection_id=collection.id,
                owner_subject="owner-a",
                query="test",
                top_k=5,
            )
    assert matches
    assert txn_flags
    assert all(flag is False for flag in txn_flags)


@pytest.mark.integration
def test_turkish_and_english_queries_use_embed_hook(
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)
    seen_queries: list[str] = []

    def capture_embed(
        text: str, *, config: EmbeddingConfig | None = None
    ) -> list[float]:
        del config
        seen_queries.append(text)
        return _basis_vector(0)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Lang")
        session.add(collection)
        session.flush()
        _add_ready_chunk(
            session,
            collection=collection,
            filename="notes.txt",
            chunk_index=0,
            text="İstanbul",
            embedding=_basis_vector(0),
        )
        session.commit()
        with patch(
            "ai_knowledge_hub_api.search.service.embed_search_query",
            side_effect=capture_embed,
        ):
            semantic_search_collection(
                session,
                collection_id=collection.id,
                owner_subject="owner-a",
                query="  İstanbul hakkında  ",
                top_k=5,
            )
            semantic_search_collection(
                session,
                collection_id=collection.id,
                owner_subject="owner-a",
                query="English query",
                top_k=5,
            )

    assert seen_queries == ["İstanbul hakkında", "English query"]


@pytest.mark.integration
def test_stable_tie_breaking_by_document_and_chunk_index(
    migrated_search_database: str,
) -> None:
    del migrated_search_database
    engine = create_engine(get_settings().resolved_database_url)
    shared = _basis_vector(0)

    with Session(engine) as session:
        collection = Collection(owner_subject="owner-a", name="Tie")
        session.add(collection)
        session.flush()
        doc = Document(
            collection_id=collection.id,
            original_filename="tie.txt",
            mime_type="text/plain",
            size_bytes=1,
            storage_key=f"k/{uuid.uuid4()}",
            status=DocumentStatus.READY,
        )
        session.add(doc)
        session.flush()
        for chunk_index in (1, 0):
            session.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk_index,
                    text=f"C{chunk_index}",
                    source_kind="text",
                    page_numbers=[1],
                    character_count=2,
                    embedding=shared,
                    embedding_model=_MODEL,
                    embedded_at=datetime.now(UTC),
                )
            )
        session.commit()
        collection_id = collection.id

    with Session(engine) as session:
        with patch(
            "ai_knowledge_hub_api.search.service.embed_search_query",
            side_effect=_mock_embed_query,
        ):
            matches = semantic_search_collection(
                session,
                collection_id=collection_id,
                owner_subject="owner-a",
                query="tie",
                top_k=10,
            )

    distances = [match.cosine_distance for match in matches]
    assert all(math.isclose(d, distances[0], abs_tol=1e-5) for d in distances)
    assert [match.chunk_index for match in matches] == [0, 1]
