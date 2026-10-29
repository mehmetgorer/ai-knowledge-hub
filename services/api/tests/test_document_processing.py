import uuid

import pytest

from ai_knowledge_hub_api.documents.processing.service import (
    DocumentProcessingFailedError,
    _extract_and_chunk,
    _load_verified_bytes,
    _snapshot_from_document,
)
from ai_knowledge_hub_api.models import Document, DocumentStatus
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage


def test_load_verified_bytes_rejects_size_mismatch(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    key = "documents/test/object"
    storage.write(key, b"abcd")
    document = Document(
        collection_id=uuid.uuid4(),
        original_filename="notes.txt",
        mime_type="text/plain",
        size_bytes=99,
        storage_key=key,
        status=DocumentStatus.UPLOADED,
    )
    snapshot = _snapshot_from_document(document)
    with pytest.raises(DocumentProcessingFailedError, match="size"):
        _load_verified_bytes(snapshot, storage)


def test_load_verified_bytes_rejects_hash_mismatch(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    key = "documents/test/object"
    storage.write(key, b"abcd")
    document = Document(
        collection_id=uuid.uuid4(),
        original_filename="notes.txt",
        mime_type="text/plain",
        size_bytes=4,
        storage_key=key,
        status=DocumentStatus.UPLOADED,
        content_hash_sha256="0" * 64,
    )
    snapshot = _snapshot_from_document(document)
    with pytest.raises(DocumentProcessingFailedError, match="hash"):
        _load_verified_bytes(snapshot, storage)


def test_extract_and_chunk_does_not_use_database_session(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    key = "documents/test/notes"
    content = b"Standalone extraction phase."
    storage.write(key, content)
    document = Document(
        collection_id=uuid.uuid4(),
        original_filename="notes.txt",
        mime_type="text/plain",
        size_bytes=len(content),
        storage_key=key,
        status=DocumentStatus.UPLOADED,
    )
    snapshot = _snapshot_from_document(document)
    result = _extract_and_chunk(snapshot, storage)
    assert result.chunks
