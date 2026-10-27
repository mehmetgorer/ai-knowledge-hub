import uuid

from sqlalchemy import inspect

from ai_knowledge_hub_api.models import Collection, Document, DocumentStatus


def test_collection_table_columns() -> None:
    mapper = inspect(Collection)
    column_names = {column.key for column in mapper.columns}
    assert column_names == {
        "id",
        "owner_subject",
        "name",
        "created_at",
        "updated_at",
    }


def test_document_table_columns_and_status_enum() -> None:
    mapper = inspect(Document)
    column_names = {column.key for column in mapper.columns}
    assert "content_hash_sha256" in column_names
    assert "status" in column_names
    assert {status.value for status in DocumentStatus} == {
        "UPLOADED",
        "PROCESSING",
        "READY",
        "FAILED",
    }


def test_collection_document_relationship() -> None:
    collection = Collection(
        owner_subject="user|verified-subject",
        name="Research",
    )
    document = Document(
        collection=collection,
        original_filename="paper.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        storage_key=f"objects/{uuid.uuid4()}",
        status=DocumentStatus.UPLOADED,
    )
    assert document.collection is collection
    assert collection.documents == [document]
