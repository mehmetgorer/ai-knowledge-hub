"""Integration tests for on-demand document processing."""

import asyncio
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
from ai_knowledge_hub_api.documents.extraction import extract_document_text
from ai_knowledge_hub_api.documents.processing import process_document
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
from tests.fixtures.extraction.pdf_builders import (
    blank_pdf_page,
    encrypted_pdf_bytes,
    pdf_with_pages,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"


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
def migrated_processing_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}processing_{uuid.uuid4().hex[:8]}"
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
    content_type: str,
) -> dict:
    response = await client.post(
        f"/collections/{collection_id}/documents",
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201
    return response.json()


async def _process(
    client: httpx.AsyncClient,
    collection_id: str,
    document_id: str,
) -> httpx.Response:
    return await client.post(
        f"/collections/{collection_id}/documents/{document_id}/process",
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_text_and_markdown_persists_chunks(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    text_body = "Merhaba dünya.\n\nİkinci paragraf."
    md_body = "# Başlık\n\nMarkdown gövde."

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        text_doc = await _upload(
            client,
            collection_id,
            "notes.txt",
            text_body.encode(),
            "text/plain",
        )
        md_doc = await _upload(
            client,
            collection_id,
            "readme.md",
            md_body.encode(),
            "text/markdown",
        )

        text_result = await _process(client, collection_id, text_doc["id"])
        assert text_result.status_code == 200
        text_payload = text_result.json()
        assert text_payload["id"] == text_doc["id"]
        assert text_payload["status"] == "PROCESSED"
        assert text_payload["chunk_count"] >= 1
        assert "text" not in text_payload

        md_result = await _process(client, collection_id, md_doc["id"])
        assert md_result.status_code == 200
        assert md_result.json()["status"] == "PROCESSED"


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_pdf_persists_page_metadata(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    pdf_bytes = pdf_with_pages(["Page one", "Page two"])

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "report.pdf",
            pdf_bytes,
            "application/pdf",
        )
        result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 200
        chunk_count = result.json()["chunk_count"]
        assert chunk_count >= 2

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        rows = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(uploaded["id"]))
            .order_by(DocumentChunk.chunk_index)
        ).all()
        assert len(rows) == chunk_count
        assert any(row.page_numbers == [1] for row in rows)
        assert any(row.page_numbers == [2] for row in rows)


@pytest.mark.integration
@pytest.mark.anyio
async def test_reprocessing_replaces_chunks_without_duplicates(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    body = "Alpha.\n\nBeta.\n\nGamma."

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "notes.txt",
            body.encode(),
            "text/plain",
        )
        first = await _process(client, collection_id, uploaded["id"])
        second = await _process(client, collection_id, uploaded["id"])
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["chunk_count"] == second.json()["chunk_count"]

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        indices = session.scalars(
            select(DocumentChunk.chunk_index).where(
                DocumentChunk.document_id == uuid.UUID(uploaded["id"])
            )
        ).all()
        assert len(indices) == len(set(indices))


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_requires_auth_and_isolates_owners(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database

    async with _client_for_subject(key_pair, "owner-a") as client_a:
        collection_id = await _create_collection(client_a)
        uploaded = await _upload(
            client_a,
            collection_id,
            "secret.txt",
            b"secret",
            "text/plain",
        )
        document_id = uploaded["id"]

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await _process(anon, collection_id, document_id)).status_code == 401

    async with _client_for_subject(key_pair, "owner-b") as client_b:
        assert (await _process(client_b, collection_id, document_id)).status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_blank_pdf_marks_failed_without_chunks(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    pdf_bytes = blank_pdf_page()

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "blank.pdf",
            pdf_bytes,
            "application/pdf",
        )
        result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 422

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        assert document.status == DocumentStatus.FAILED
        assert (
            session.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            is None
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_encrypted_pdf_marks_failed(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    pdf_bytes = encrypted_pdf_bytes()

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "locked.pdf",
            pdf_bytes,
            "application/pdf",
        )
        result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 422

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        assert document.status == DocumentStatus.FAILED


@pytest.mark.integration
@pytest.mark.anyio
async def test_process_missing_storage_marks_failed(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "notes.txt",
            b"hello",
            "text/plain",
        )

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        storage = document_storage_for_settings(get_settings())
        storage.delete(document.storage_key)

    async with _client_for_subject(key_pair, "owner-a") as client:
        result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 422

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        assert document.status == DocumentStatus.FAILED


@pytest.mark.integration
@pytest.mark.anyio
async def test_failed_processing_preserves_existing_chunks_on_reprocess(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "notes.txt",
            b"Keep these chunks.",
            "text/plain",
        )
        assert (
            await _process(client, collection_id, uploaded["id"])
        ).status_code == 200

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        before = session.scalars(
            select(DocumentChunk.text).where(
                DocumentChunk.document_id == uuid.UUID(uploaded["id"])
            )
        ).all()
        assert before

    def fail_extract(*_args, **_kwargs):
        raise RuntimeError("simulated extract failure")

    async with _client_for_subject(key_pair, "owner-a") as client:
        with patch(
            "ai_knowledge_hub_api.documents.processing.service.extract_document_text",
            fail_extract,
        ):
            result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 422

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        assert document.status == DocumentStatus.FAILED
        after = session.scalars(
            select(DocumentChunk.text).where(DocumentChunk.document_id == document.id)
        ).all()
        assert list(after) == list(before)


@pytest.mark.integration
@pytest.mark.anyio
async def test_concurrent_processing_returns_conflict(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "slow.txt",
            b"Slow processing text.",
            "text/plain",
        )
        document_id = uploaded["id"]

        def slow_extract(*_args, **_kwargs):
            import time

            time.sleep(0.3)
            return extract_document_text(
                b"Slow processing text.",
                filename="slow.txt",
            )

        with patch(
            "ai_knowledge_hub_api.documents.processing.service.extract_document_text",
            slow_extract,
        ):
            first = asyncio.create_task(_process(client, collection_id, document_id))
            await asyncio.sleep(0.05)
            second = await _process(client, collection_id, document_id)
            first_response = await first

        assert first_response.status_code == 200
        assert second.status_code == 409


@pytest.mark.integration
@pytest.mark.anyio
async def test_ready_documents_cannot_be_processed(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        uploaded = await _upload(
            client,
            collection_id,
            "ready.txt",
            b"ready",
            "text/plain",
        )

    engine = create_engine(get_settings().resolved_database_url)
    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(uploaded["id"]))
        assert document is not None
        document.status = DocumentStatus.READY
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        result = await _process(client, collection_id, uploaded["id"])
        assert result.status_code == 409


@pytest.mark.integration
def test_extraction_runs_without_active_db_transaction(
    migrated_processing_database: str,
) -> None:
    del migrated_processing_database
    settings = get_settings()
    engine = create_engine(settings.resolved_database_url)
    storage = document_storage_for_settings(settings)
    content = b"Transaction idle during extract."

    txn_during_extract: list[bool] = []
    processing_session: Session | None = None

    def track_extract(*args, **kwargs):
        assert processing_session is not None
        txn_during_extract.append(processing_session.in_transaction())
        return extract_document_text(*args, **kwargs)

    with patch(
        "ai_knowledge_hub_api.documents.processing.service.extract_document_text",
        track_extract,
    ):
        with Session(engine) as session:
            processing_session = session
            collection = Collection(owner_subject="provider|txn-test", name="Txn")
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

    assert txn_during_extract
    assert all(flag is False for flag in txn_during_extract)
