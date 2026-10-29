"""Integration tests for document chunk PostgreSQL persistence."""

import uuid

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.documents.chunking.types import TextChunk
from ai_knowledge_hub_api.documents.chunks.persistence import (
    ChunkPersistenceError,
    load_document_chunks,
    replace_document_chunks,
)
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from ai_knowledge_hub_api.models import (
    Collection,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from tests.alembic_test_support import (
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
    read_alembic_revision,
    run_alembic,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


@pytest.fixture
def migrated_chunks_database() -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}chunks_{uuid.uuid4().hex[:8]}"
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
        assert "document_chunks" in inspector.get_table_names()
        unique = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("document_chunks")
        }
        assert "uq_document_chunks_document_id_chunk_index" in unique
        indexes = {index["name"] for index in inspector.get_indexes("document_chunks")}
        assert "ix_document_chunks_document_id" in indexes

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


def _insert_document(session: Session) -> Document:
    collection = Collection(owner_subject="provider|chunk-test", name="Chunks")
    session.add(collection)
    session.flush()
    document = Document(
        collection_id=collection.id,
        original_filename="notes.md",
        mime_type="text/markdown",
        size_bytes=128,
        storage_key=f"storage/{uuid.uuid4()}",
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    session.flush()
    return document


@pytest.mark.integration
def test_persist_and_reload_chunks_in_order(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        loaded = load_document_chunks(session, document_id)
    assert loaded == chunks


@pytest.mark.integration
def test_duplicate_chunk_index_rejected(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                text="conflict",
                source_kind="text",
                page_numbers=[1],
                character_count=8,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.integration
def test_document_deletion_cascades_to_chunks(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    chunks = _sample_chunks()

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=chunks)
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        session.delete(document)
        session.commit()
        remaining = session.scalar(select(DocumentChunk))
        assert remaining is None


@pytest.mark.integration
def test_atomic_replace_and_rollback(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    original = _sample_chunks()
    replacement = (
        TextChunk(
            chunk_index=0,
            text="Replacement chunk only.",
            source_kind="text",
            page_numbers=(1,),
            character_count=len("Replacement chunk only."),
        ),
    )

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=original)
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        replace_document_chunks(
            session,
            document_id=document_id,
            chunks=replacement,
        )
        session.rollback()

    with Session(engine) as session:
        loaded = load_document_chunks(session, document_id)
    assert loaded == original


@pytest.mark.integration
def test_replace_commits_new_set_atomically(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    original = _sample_chunks()
    replacement = (
        TextChunk(
            chunk_index=0,
            text="Only new content.",
            source_kind="text",
            page_numbers=(4,),
            character_count=len("Only new content."),
        ),
    )

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=original)
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
        loaded = load_document_chunks(session, document_id)
    assert loaded == replacement


@pytest.mark.integration
def test_batch_duplicate_index_rejected_before_delete(
    migrated_chunks_database: str,
) -> None:
    engine = create_engine(migrated_chunks_database)
    original = _sample_chunks()
    bad_batch = (
        TextChunk(0, "a", "text", (1,), 1),
        TextChunk(0, "b", "text", (1,), 1),
    )

    with Session(engine) as session:
        document = _insert_document(session)
        replace_document_chunks(session, document_id=document.id, chunks=original)
        session.commit()
        document_id = document.id

    with Session(engine) as session:
        with pytest.raises(ChunkPersistenceError):
            replace_document_chunks(
                session,
                document_id=document_id,
                chunks=bad_batch,
            )
        session.rollback()

    with Session(engine) as session:
        loaded = load_document_chunks(session, document_id)
    assert loaded == original


@pytest.mark.integration
def test_chunks_isolated_between_documents(migrated_chunks_database: str) -> None:
    engine = create_engine(migrated_chunks_database)
    chunks_a = _sample_chunks()
    chunks_b = (
        TextChunk(
            chunk_index=0,
            text="Document B chunk.",
            source_kind="text",
            page_numbers=(1,),
            character_count=len("Document B chunk."),
        ),
    )

    with Session(engine) as session:
        doc_a = _insert_document(session)
        doc_b = _insert_document(session)
        replace_document_chunks(session, document_id=doc_a.id, chunks=chunks_a)
        replace_document_chunks(session, document_id=doc_b.id, chunks=chunks_b)
        session.commit()
        id_a, id_b = doc_a.id, doc_b.id

    with Session(engine) as session:
        assert load_document_chunks(session, id_a) == chunks_a
        assert load_document_chunks(session, id_b) == chunks_b
