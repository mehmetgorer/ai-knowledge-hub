import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import Settings, get_settings
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


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


@pytest.mark.integration
def test_migrated_schema_constraints_and_relationships() -> None:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}schema_{uuid.uuid4().hex[:8]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        result = run_alembic("upgrade", "head", database_url=temp_url)
        assert result.returncode == 0, result.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        engine = create_engine(temp_url)
        with engine.connect() as connection:
            vector = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            assert vector is not None

        with Session(engine) as session:
            collection_a = Collection(
                owner_subject="provider|user-a",
                name="Team A",
            )
            collection_b = Collection(
                owner_subject="provider|user-b",
                name="Team B",
            )
            session.add_all([collection_a, collection_b])
            session.flush()

            document = Document(
                collection_id=collection_a.id,
                original_filename="notes.txt",
                mime_type="text/plain",
                size_bytes=12,
                storage_key=f"storage/{uuid.uuid4()}",
                status=DocumentStatus.UPLOADED,
                content_hash_sha256="a" * 64,
            )
            session.add(document)
            session.commit()

            orphan = Document(
                collection_id=uuid.uuid4(),
                original_filename="orphan.txt",
                mime_type="text/plain",
                size_bytes=1,
                storage_key=f"storage/{uuid.uuid4()}",
            )
            session.add(orphan)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.delete(collection_a)
            session.commit()

            remaining = session.scalar(select(Document))
            assert remaining is None

            still_there = session.scalar(
                select(Collection).where(Collection.id == collection_b.id)
            )
            assert still_there is not None
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
