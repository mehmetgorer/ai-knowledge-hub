"""Integration tests for DELETE /collections/{id}/documents/{id}."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.models import Document, DocumentChunk, DocumentStatus
from ai_knowledge_hub_api.storage.dependencies import document_storage_for_settings
from tests.auth_keys import Ed25519KeyPair
from tests.test_documents_integration import (
    _client_for_subject,
    _create_collection,
)
from tests.test_semantic_search_integration import _basis_vector, _mock_embed_query

pytest_plugins = ["tests.test_documents_integration"]

_SEARCH_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


@pytest.mark.integration
@pytest.mark.anyio
async def test_delete_document_removes_record_chunks_and_file(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database
    engine = create_engine(get_settings().resolved_database_url)
    content = b"hello chunk text"

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        upload = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("notes.txt", content, "text/plain")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                text="hello chunk text",
                source_kind="text",
                page_numbers=[1],
                character_count=16,
                embedding=_basis_vector(0),
                embedding_model=_SEARCH_EMBEDDING_MODEL,
                embedded_at=datetime.now(UTC),
            ),
        )
        document.status = DocumentStatus.READY
        session.commit()
        storage_key = document.storage_key

    storage = document_storage_for_settings(get_settings())
    assert storage.read(storage_key) == content

    async with _client_for_subject(key_pair, "owner-a") as client:
        response = await client.delete(
            f"/collections/{collection_id}/documents/{document_id}",
        )

    assert response.status_code == 204

    with Session(engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is None
        chunk_count = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id)),
        )
        assert chunk_count == 0

    with pytest.raises(FileNotFoundError):
        storage.read(storage_key)

    async with _client_for_subject(key_pair, "owner-a") as client:
        listed = await client.get(f"/collections/{collection_id}/documents")
        assert listed.json() == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_delete_document_cross_user_forbidden(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "owner-a") as client_a:
        collection_id = await _create_collection(client_a)
        upload = await client_a.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("secret.txt", b"x", "text/plain")},
        )
        document_id = upload.json()["id"]

    async with _client_for_subject(key_pair, "owner-b") as client_b:
        response = await client_b.delete(
            f"/collections/{collection_id}/documents/{document_id}",
        )
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_delete_nonexistent_document_returns_404(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        missing_id = "00000000-0000-0000-0000-000000000099"
        response = await client.delete(
            f"/collections/{collection_id}/documents/{missing_id}",
        )
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_delete_rejects_processing_document(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database
    engine = create_engine(get_settings().resolved_database_url)

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        upload = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("busy.txt", b"x", "text/plain")},
        )
        document_id = upload.json()["id"]

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        document.status = DocumentStatus.PROCESSING
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        response = await client.delete(
            f"/collections/{collection_id}/documents/{document_id}",
        )
        assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_excludes_deleted_document_chunks(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database
    engine = create_engine(get_settings().resolved_database_url)

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        upload = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("findme.txt", b"x", "text/plain")},
        )
        document_id = upload.json()["id"]

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                text="unique alpha beta retrieval phrase",
                source_kind="text",
                page_numbers=[1],
                character_count=33,
                embedding=_basis_vector(0),
                embedding_model=_SEARCH_EMBEDDING_MODEL,
                embedded_at=datetime.now(UTC),
            ),
        )
        document.status = DocumentStatus.READY
        session.commit()

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=_mock_embed_query,
    ):
        async with _client_for_subject(key_pair, "owner-a") as client:
            before = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "alpha beta", "top_k": 5},
            )
            assert before.status_code == 200
            assert len(before.json()["matches"]) == 1

            deleted = await client.delete(
                f"/collections/{collection_id}/documents/{document_id}",
            )
            assert deleted.status_code == 204

            after = await client.post(
                f"/collections/{collection_id}/search",
                json={"query": "alpha beta", "top_k": 5},
            )
            assert after.status_code == 200
            assert after.json()["matches"] == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_delete_returns_503_when_database_commit_fails(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database
    engine = create_engine(get_settings().resolved_database_url)

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_id = await _create_collection(client)
        upload = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("keep.txt", b"data", "text/plain")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        storage_key = document.storage_key

    def boom(self):
        raise RuntimeError("simulated delete commit failure")

    async with _client_for_subject(key_pair, "owner-a") as client:
        with patch.object(Session, "commit", boom):
            response = await client.delete(
                f"/collections/{collection_id}/documents/{document_id}",
            )
        assert response.status_code == 503

    with Session(engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is not None

    storage = document_storage_for_settings(get_settings())
    assert storage.read(storage_key) == b"data"
