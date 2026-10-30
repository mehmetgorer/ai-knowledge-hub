"""Regression tests for cross-user and cross-collection authorization."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.models import Document, DocumentStatus
from tests.auth_keys import Ed25519KeyPair
from tests.test_documents_integration import (
    _client_for_subject,
    _create_collection,
)

pytest_plugins = ["tests.test_documents_integration"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_document_in_wrong_collection_returns_404_for_process_index_delete(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    """Document IDs from collection A must not be actionable under collection B."""
    del migrated_documents_database
    engine = create_engine(get_settings().resolved_database_url)

    async with _client_for_subject(key_pair, "owner-a") as client:
        collection_a = await _create_collection(client, name="Collection A")
        collection_b = await _create_collection(client, name="Collection B")
        upload = await client.post(
            f"/collections/{collection_a}/documents",
            files={"file": ("owned.txt", b"secret", "text/plain")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

    with Session(engine) as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        document.status = DocumentStatus.PROCESSED
        session.commit()

    async with _client_for_subject(key_pair, "owner-a") as client:
        process = await client.post(
            f"/collections/{collection_b}/documents/{document_id}/process",
        )
        assert process.status_code == 404

        index = await client.post(
            f"/collections/{collection_b}/documents/{document_id}/index",
        )
        assert index.status_code == 404

        delete = await client.delete(
            f"/collections/{collection_b}/documents/{document_id}",
        )
        assert delete.status_code == 404

    with Session(engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is not None


@pytest.mark.integration
@pytest.mark.anyio
async def test_list_documents_does_not_leak_other_users_collections(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_documents_database: str,
) -> None:
    del migrated_documents_database

    async with _client_for_subject(key_pair, "user-a") as client_a:
        collection_id = await _create_collection(client_a)
        upload = await client_a.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("private.txt", b"x", "text/plain")},
        )
        assert upload.status_code == 201

    async with _client_for_subject(key_pair, "user-b") as client_b:
        listed = await client_b.get(f"/collections/{collection_id}/documents")
        assert listed.status_code == 404
