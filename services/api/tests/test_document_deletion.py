"""Unit tests for document deletion service."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.documents.deletion import (
    DocumentDeletionConflictError,
    delete_owned_document,
)
from ai_knowledge_hub_api.models import Document, DocumentStatus
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage


def _document(*, status: DocumentStatus) -> Document:
    return Document(
        id=uuid.uuid4(),
        collection_id=uuid.uuid4(),
        original_filename="a.txt",
        mime_type="text/plain",
        size_bytes=4,
        storage_key="collections/x/documents/y.bin",
        status=status,
    )


def test_blocks_delete_while_processing() -> None:
    db = MagicMock(spec=Session)
    storage = MagicMock(spec=LocalDocumentStorage)
    document = _document(status=DocumentStatus.PROCESSING)
    execute_result = MagicMock()
    execute_result.first.return_value = None
    db.execute.return_value = execute_result
    db.scalar.return_value = DocumentStatus.PROCESSING
    with pytest.raises(DocumentDeletionConflictError):
        delete_owned_document(
            db,
            document=document,
            storage=storage,
        )
    storage.delete.assert_not_called()


def test_blocks_delete_while_indexing() -> None:
    db = MagicMock(spec=Session)
    storage = MagicMock(spec=LocalDocumentStorage)
    document = _document(status=DocumentStatus.INDEXING)
    execute_result = MagicMock()
    execute_result.first.return_value = None
    db.execute.return_value = execute_result
    db.scalar.return_value = DocumentStatus.INDEXING
    with pytest.raises(DocumentDeletionConflictError):
        delete_owned_document(
            db,
            document=document,
            storage=storage,
        )


def test_deletes_db_before_storage() -> None:
    db = MagicMock(spec=Session)
    storage = MagicMock(spec=LocalDocumentStorage)
    document = _document(status=DocumentStatus.READY)
    execute_result = MagicMock()
    execute_result.first.return_value = (document.storage_key,)
    db.execute.return_value = execute_result
    delete_owned_document(db, document=document, storage=storage)
    db.execute.assert_called_once()
    db.delete.assert_not_called()
    db.commit.assert_called_once()
    storage.delete.assert_called_once_with(document.storage_key)


def test_rolls_back_db_without_touching_storage_on_commit_failure() -> None:
    db = MagicMock(spec=Session)
    document = _document(status=DocumentStatus.UPLOADED)
    execute_result = MagicMock()
    execute_result.first.return_value = (document.storage_key,)
    db.execute.return_value = execute_result
    db.commit.side_effect = RuntimeError("db down")
    storage = MagicMock(spec=LocalDocumentStorage)
    with pytest.raises(RuntimeError):
        delete_owned_document(db, document=document, storage=storage)
    db.rollback.assert_called()
    storage.delete.assert_not_called()
