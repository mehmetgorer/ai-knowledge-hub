"""Integration tests for chunk embedding PostgreSQL persistence."""

import math
import uuid
from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.documents.chunking.types import TextChunk
from ai_knowledge_hub_api.documents.chunks.persistence import (
    load_document_chunks,
    replace_document_chunks,
)
from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import InvalidEmbeddingVectorError
from ai_knowledge_hub_api.embeddings.persistence import (
    ChunkEmbeddingInput,
    ChunkEmbeddingPersistenceError,
    load_document_chunk_embeddings,
    persist_document_chunk_embeddings,
)
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from ai_knowledge_hub_api.models import Collection, Document, DocumentStatus
from tests.alembic_test_support import (
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
    read_alembic_revision,
    run_alembic,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"
_MODEL = EmbeddingConfig().model_name


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


@pytest.fixture
def migrated_embeddings_database() -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}emb_{uuid.uuid4().hex[:8]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        result = run_alembic("upgrade", "head", database_url=temp_url)
        assert result.returncode == 0, result.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        engine = create_engine(temp_url)
        inspector = inspect(engine)
        columns = {
            column["name"] for column in inspector.get_columns("document_chunks")
        }
        assert {"embedding", "embedding_model", "embedded_at"}.issubset(columns)

        yield temp_url
    finally:
        get_settings.cache_clear()
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


def _unit_vector(seed: int, *, dimensions: int = 384) -> tuple[float, ...]:
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(dimensions)
    normalized = vector / np.linalg.norm(vector)
    return tuple(float(value) for value in normalized)


def _sample_chunks() -> tuple[TextChunk, ...]:
    return (
        TextChunk(
            chunk_index=0,
            text="İstanbul'da örnek paragraf.",
            source_kind="markdown",
            page_numbers=(1,),
            character_count=len("İstanbul'da örnek paragraf."),
        ),
        TextChunk(
            chunk_index=1,
            text="Second chunk on pages two and three.",
            source_kind="pdf",
            page_numbers=(2, 3),
            character_count=len("Second chunk on pages two and three."),
        ),
    )


def _insert_processed_document(session: Session) -> Document:
    collection = Collection(owner_subject="provider|emb-test", name="Embeddings")
    session.add(collection)
    session.flush()
    document = Document(
        collection_id=collection.id,
        original_filename="notes.md",
        mime_type="text/markdown",
        size_bytes=128,
        storage_key=f"storage/{uuid.uuid4()}",
        status=DocumentStatus.PROCESSED,
    )
    session.add(document)
    session.flush()
    return document


def _embedding_inputs_for_chunks(
    chunks: tuple[TextChunk, ...],
) -> tuple[ChunkEmbeddingInput, ...]:
    return tuple(
        ChunkEmbeddingInput(
            chunk_index=chunk.chunk_index, vector=_unit_vector(chunk.chunk_index)
        )
        for chunk in chunks
    )


@pytest.mark.integration
def test_migration_preserves_existing_chunks_without_embeddings(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        loaded_text = load_document_chunks(session, document_id)
        loaded_emb = load_document_chunk_embeddings(session, document_id)
    assert loaded_text == chunks
    assert loaded_emb == ()


@pytest.mark.integration
def test_persist_and_reload_embeddings_round_trip(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()
    inputs = _embedding_inputs_for_chunks(chunks)
    stamp = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        persist_document_chunk_embeddings(
            session,
            document_id=document.id,
            embeddings=inputs,
            embedding_model=_MODEL,
            embedded_at=stamp,
        )
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        stored = load_document_chunk_embeddings(session, document_id)
        text_rows = load_document_chunks(session, document_id)

    assert text_rows == chunks
    assert len(stored) == 2
    assert stored[0].chunk_index == 0
    assert stored[0].embedding_model == _MODEL
    assert stored[0].embedded_at == stamp
    assert len(stored[0].vector) == 384
    for original, loaded in zip(inputs, stored, strict=True):
        assert original.chunk_index == loaded.chunk_index
        for a, b in zip(original.vector, loaded.vector, strict=True):
            assert math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)


@pytest.mark.integration
def test_rejects_wrong_status(migrated_embeddings_database: str) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()
    inputs = _embedding_inputs_for_chunks(chunks)

    with Session(engine) as session:
        collection = Collection(owner_subject="x", name="y")
        session.add(collection)
        session.flush()
        document = Document(
            collection_id=collection.id,
            original_filename="a.md",
            mime_type="text/markdown",
            size_bytes=1,
            storage_key=f"k/{uuid.uuid4()}",
            status=DocumentStatus.UPLOADED,
        )
        session.add(document)
        session.flush()
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        with pytest.raises(ChunkEmbeddingPersistenceError, match="PROCESSED"):
            persist_document_chunk_embeddings(
                session,
                document_id=document.id,
                embeddings=inputs,
                embedding_model=_MODEL,
            )
        session.rollback()


@pytest.mark.integration
def test_rejects_missing_and_duplicate_indices(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    missing = (ChunkEmbeddingInput(0, _unit_vector(0)),)
    with Session(engine) as session:
        with pytest.raises(ChunkEmbeddingPersistenceError, match="missing indices"):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=missing,
                embedding_model=_MODEL,
            )
        session.rollback()

    duplicate = (
        ChunkEmbeddingInput(0, _unit_vector(0)),
        ChunkEmbeddingInput(0, _unit_vector(1)),
    )
    with Session(engine) as session:
        with pytest.raises(ChunkEmbeddingPersistenceError, match="Duplicate"):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=duplicate,
                embedding_model=_MODEL,
            )
        session.rollback()


@pytest.mark.integration
def test_rejects_wrong_vector_dimensions(migrated_embeddings_database: str) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    inputs = (
        ChunkEmbeddingInput(0, tuple(0.0 for _ in range(10))),
        ChunkEmbeddingInput(1, _unit_vector(1)),
    )
    with Session(engine) as session:
        with pytest.raises(InvalidEmbeddingVectorError):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=inputs,
                embedding_model=_MODEL,
            )
        session.rollback()


@pytest.mark.integration
def test_rejects_non_finite_vectors(migrated_embeddings_database: str) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    bad = list(_unit_vector(0))
    bad[0] = float("nan")
    inputs = (
        ChunkEmbeddingInput(0, tuple(bad)),
        ChunkEmbeddingInput(1, _unit_vector(1)),
    )
    with Session(engine) as session:
        with pytest.raises(InvalidEmbeddingVectorError):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=inputs,
                embedding_model=_MODEL,
            )
        session.rollback()


@pytest.mark.integration
def test_rejects_non_normalized_vectors(migrated_embeddings_database: str) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    inputs = (
        ChunkEmbeddingInput(0, tuple(1.0 for _ in range(384))),
        ChunkEmbeddingInput(1, _unit_vector(1)),
    )
    with Session(engine) as session:
        with pytest.raises(InvalidEmbeddingVectorError):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=inputs,
                embedding_model=_MODEL,
            )
        session.rollback()


@pytest.mark.integration
def test_failed_persist_rolls_back_prior_embeddings(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()
    good = _embedding_inputs_for_chunks(chunks)

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        persist_document_chunk_embeddings(
            session,
            document_id=document.id,
            embeddings=good,
            embedding_model=_MODEL,
        )
        session.commit()
        document_id = document.id

    bad = (
        ChunkEmbeddingInput(0, _unit_vector(99)),
        ChunkEmbeddingInput(1, (float("inf"),) + _unit_vector(1)[1:]),
    )
    with Session(engine) as session:
        with pytest.raises(InvalidEmbeddingVectorError):
            persist_document_chunk_embeddings(
                session,
                document_id=document_id,
                embeddings=bad,
                embedding_model=_MODEL,
            )
        session.rollback()

    with Session(engine) as session:
        stored = load_document_chunk_embeddings(session, document_id)
    assert len(stored) == 2
    for original, loaded in zip(good, stored, strict=True):
        assert original.chunk_index == loaded.chunk_index
        for a, b in zip(original.vector, loaded.vector, strict=True):
            assert math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)


@pytest.mark.integration
def test_replace_document_chunks_removes_embeddings(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    original = _sample_chunks()
    replacement = (
        TextChunk(
            chunk_index=0,
            text="Replacement only.",
            source_kind="text",
            page_numbers=(9,),
            character_count=len("Replacement only."),
        ),
    )

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=original)
        persist_document_chunk_embeddings(
            session,
            document_id=document.id,
            embeddings=_embedding_inputs_for_chunks(original),
            embedding_model=_MODEL,
        )
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        replace_document_chunks(
            session,
            document_id=document_id,
            chunks=replacement,
        )
        session.commit()

    with Session(engine) as session:
        assert load_document_chunk_embeddings(session, document_id) == ()
        assert load_document_chunks(session, document_id) == replacement


@pytest.mark.integration
def test_embeddings_isolated_between_documents(
    migrated_embeddings_database: str,
) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks_a = _sample_chunks()
    chunks_b = (
        TextChunk(
            chunk_index=0,
            text="Doc B.",
            source_kind="text",
            page_numbers=(1,),
            character_count=len("Doc B."),
        ),
    )

    with Session(engine) as session:
        doc_a = _insert_processed_document(session)
        doc_b = _insert_processed_document(session)
        replace_document_chunks(session, document_id=doc_a.id, chunks=chunks_a)
        replace_document_chunks(session, document_id=doc_b.id, chunks=chunks_b)
        persist_document_chunk_embeddings(
            session,
            document_id=doc_a.id,
            embeddings=_embedding_inputs_for_chunks(chunks_a),
            embedding_model=_MODEL,
        )
        persist_document_chunk_embeddings(
            session,
            document_id=doc_b.id,
            embeddings=_embedding_inputs_for_chunks(chunks_b),
            embedding_model=_MODEL,
        )
        session.commit()
        id_a, id_b = doc_a.id, doc_b.id

    with Session(engine) as session:
        emb_a = load_document_chunk_embeddings(session, id_a)
        emb_b = load_document_chunk_embeddings(session, id_b)
    assert len(emb_a) == 2
    assert len(emb_b) == 1
    assert emb_a[0].chunk_index == 0
    assert emb_b[0].chunk_index == 0


@pytest.mark.integration
def test_rejects_wrong_embedding_model(migrated_embeddings_database: str) -> None:
    engine = create_engine(migrated_embeddings_database)
    chunks = _sample_chunks()
    inputs = _embedding_inputs_for_chunks(chunks)

    with Session(engine) as session:
        document = _insert_processed_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        with pytest.raises(ChunkEmbeddingPersistenceError, match="embedding_model"):
            persist_document_chunk_embeddings(
                session,
                document_id=document.id,
                embeddings=inputs,
                embedding_model="wrong/model",
            )
        session.rollback()
