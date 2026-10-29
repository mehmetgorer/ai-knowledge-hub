"""Unit tests for document upload validation and local storage."""

import uuid

import pytest

from ai_knowledge_hub_api.documents.validation import (
    DocumentUploadValidationError,
    generate_storage_key,
    validate_upload_content,
)
from ai_knowledge_hub_api.storage.local import (
    LocalDocumentStorage,
    UnsafeStorageKeyError,
)


def test_validate_accepts_minimal_pdf() -> None:
    data = b"%PDF-1.4\n%%EOF\n"
    result = validate_upload_content(filename="paper.pdf", data=data)
    assert result.mime_type == "application/pdf"
    assert result.original_filename == "paper.pdf"
    assert len(result.content_hash_sha256) == 64


def test_validate_accepts_utf8_text_and_markdown() -> None:
    txt = validate_upload_content(filename="notes.txt", data=b"hello")
    assert txt.mime_type == "text/plain"
    md = validate_upload_content(filename="readme.md", data=b"# Title")
    assert md.mime_type == "text/markdown"


def test_validate_rejects_empty_file() -> None:
    with pytest.raises(DocumentUploadValidationError, match="empty"):
        validate_upload_content(filename="x.txt", data=b"")


def test_validate_rejects_unsupported_extension() -> None:
    with pytest.raises(DocumentUploadValidationError, match="Unsupported"):
        validate_upload_content(filename="image.png", data=b"\x89PNG")


def test_validate_rejects_pdf_extension_without_pdf_magic() -> None:
    with pytest.raises(DocumentUploadValidationError, match="PDF"):
        validate_upload_content(filename="fake.pdf", data=b"not a pdf")


def test_validate_rejects_text_with_nul_bytes() -> None:
    with pytest.raises(DocumentUploadValidationError):
        validate_upload_content(filename="bad.txt", data=b"a\x00b")


def test_validate_uses_safe_basename_only() -> None:
    result = validate_upload_content(
        filename="../../etc/passwd.txt",
        data=b"safe",
    )
    assert result.original_filename == "passwd.txt"


def test_generate_storage_key_is_collection_scoped() -> None:
    cid = uuid.uuid4()
    key = generate_storage_key(cid)
    assert key.startswith(f"documents/{cid}/")
    assert ".." not in key


def test_local_storage_rejects_traversal_keys(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    with pytest.raises(UnsafeStorageKeyError):
        storage.resolve_key_path("../outside")
    with pytest.raises(UnsafeStorageKeyError):
        storage.resolve_key_path("documents/../../etc/passwd")


def test_local_storage_write_and_delete(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    key = "documents/test/id"
    storage.write(key, b"payload")
    path = storage.resolve_key_path(key)
    assert path.read_bytes() == b"payload"
    storage.delete(key)
    assert not path.is_file()
