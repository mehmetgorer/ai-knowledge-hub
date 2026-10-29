import uuid

import pytest

from ai_knowledge_hub_api.documents.processing.service import (
    DocumentProcessingFailedError,
    _load_verified_bytes,
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
    with pytest.raises(DocumentProcessingFailedError, match="size"):
        _load_verified_bytes(document, storage)


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
    with pytest.raises(DocumentProcessingFailedError, match="hash"):
        _load_verified_bytes(document, storage)
