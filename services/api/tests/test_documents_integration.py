"""Integration tests for document upload and listing (temporary DB + filesystem)."""

import uuid
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
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
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
def migrated_documents_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}documents_{uuid.uuid4().hex[:8]}"
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


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_and_list_documents_persisted(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database
    pdf_bytes = b"%PDF-1.4\n%%EOF\n"

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        upload = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload.status_code == 201
        body = upload.json()
        assert body["collection_id"] == collection_id
        assert body["original_filename"] == "report.pdf"
        assert body["mime_type"] == "application/pdf"
        assert body["size_bytes"] == len(pdf_bytes)
        assert body["status"] == "UPLOADED"
        assert body["content_hash_sha256"]
        assert "storage_key" not in body

        listed = await client.get(f"/collections/{collection_id}/documents")
        assert listed.status_code == 200
        items = listed.json()
        assert len(items) == 1
        assert items[0]["id"] == body["id"]
        assert "storage_key" not in items[0]

        storage = document_storage_for_settings(get_settings())
        stored_files = [p for p in storage.root.rglob("*") if p.is_file()]
        assert len(stored_files) == 1
        assert stored_files[0].read_bytes() == pdf_bytes


@pytest.mark.integration
@pytest.mark.anyio
async def test_documents_collection_ownership_isolation(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "owner-a") as client_a:
        collection_id = await _create_collection(client_a)

    async with _client_for_subject(key_pair, "owner-b") as client_b:
        upload = await client_b.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("notes.txt", b"secret", "text/plain")},
        )
        assert upload.status_code == 404

        listed = await client_b.get(f"/collections/{collection_id}/documents")
        assert listed.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_rejects_empty_and_invalid_types(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)

        empty = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert empty.status_code == 400

        wrong_type = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("photo.png", b"\x89PNG", "image/png")},
        )
        assert wrong_type.status_code == 400

        fake_pdf = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("bad.pdf", b"not-pdf", "application/pdf")},
        )
        assert fake_pdf.status_code == 400


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_rejects_oversized_file(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_documents_database
    monkeypatch.setenv("DOCUMENT_MAX_UPLOAD_BYTES", "32")
    get_settings.cache_clear()
    dispose_engine()

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        too_large = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("big.txt", b"x" * 64, "text/plain")},
        )
        assert too_large.status_code == 413


@pytest.mark.integration
@pytest.mark.anyio
async def test_storage_file_removed_when_database_commit_fails(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        storage = document_storage_for_settings(get_settings())

        def boom(self):
            raise RuntimeError("simulated persistence failure")

        with patch.object(Session, "commit", boom):
            with pytest.raises(RuntimeError, match="simulated persistence failure"):
                await client.post(
                    f"/collections/{collection_id}/documents",
                    files={"file": ("notes.txt", b"hello", "text/plain")},
                )

        files_after = [p for p in storage.root.rglob("*") if p.is_file()]
        assert files_after == []

        listed = await client.get(f"/collections/{collection_id}/documents")
        assert listed.json() == []
