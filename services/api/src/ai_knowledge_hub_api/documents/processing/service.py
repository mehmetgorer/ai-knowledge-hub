"""On-demand document extract/chunk/persist pipeline."""

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.documents.chunking import chunk_extraction_result
from ai_knowledge_hub_api.documents.chunking.errors import ChunkingError
from ai_knowledge_hub_api.documents.chunks.persistence import (
    ChunkPersistenceError,
    replace_document_chunks,
)
from ai_knowledge_hub_api.documents.extraction import extract_document_text
from ai_knowledge_hub_api.documents.extraction.errors import DocumentExtractionError
from ai_knowledge_hub_api.models import Document, DocumentChunk, DocumentStatus
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage

logger = logging.getLogger(__name__)

_ELIGIBLE_FOR_PROCESSING = frozenset(
    {
        DocumentStatus.UPLOADED,
        DocumentStatus.FAILED,
        DocumentStatus.PROCESSED,
    }
)


class DocumentProcessingConflictError(Exception):
    """Document cannot be claimed for processing (concurrency or status)."""


class DocumentProcessingFailedError(Exception):
    """Extraction, chunking, or persistence failed."""

    def __init__(self, message: str, *, code: str = "processing_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class DocumentProcessResult:
    document_id: uuid.UUID
    status: DocumentStatus
    chunk_count: int


@dataclass(frozen=True)
class _DocumentProcessingSnapshot:
    document_id: uuid.UUID
    collection_id: uuid.UUID
    original_filename: str
    storage_key: str
    size_bytes: int
    content_hash_sha256: str | None


def _snapshot_from_document(document: Document) -> _DocumentProcessingSnapshot:
    return _DocumentProcessingSnapshot(
        document_id=document.id,
        collection_id=document.collection_id,
        original_filename=document.original_filename,
        storage_key=document.storage_key,
        size_bytes=document.size_bytes,
        content_hash_sha256=document.content_hash_sha256,
    )


def process_document(
    db: Session,
    *,
    document: Document,
    storage: LocalDocumentStorage,
) -> DocumentProcessResult:
    """
    Claim the document, extract/chunk outside a long DB transaction, then persist.

    Caller supplies an owned ``document`` row. Commits status transitions; on failure
    marks FAILED without removing previously committed chunks.
    """
    snapshot = _snapshot_from_document(document)
    if not _claim_for_processing(db, snapshot.document_id, snapshot.collection_id):
        db.rollback()
        _raise_claim_conflict(db, snapshot.document_id, snapshot.collection_id)
    db.commit()

    try:
        chunking = _extract_and_chunk(snapshot, storage)
    except (
        DocumentExtractionError,
        ChunkingError,
        ChunkPersistenceError,
        DocumentProcessingFailedError,
        FileNotFoundError,
        OSError,
    ) as exc:
        logger.warning(
            "Document processing failed document_id=%s code=%s",
            snapshot.document_id,
            getattr(exc, "code", type(exc).__name__),
        )
        _mark_failed(db, snapshot.document_id)
        db.commit()
        if isinstance(exc, DocumentProcessingFailedError):
            raise
        raise DocumentProcessingFailedError(
            "Document processing failed",
            code=getattr(exc, "code", "processing_failed"),
        ) from exc
    except Exception as exc:
        logger.warning(
            "Document processing failed document_id=%s error_type=%s",
            snapshot.document_id,
            type(exc).__name__,
        )
        _mark_failed(db, snapshot.document_id)
        db.commit()
        raise DocumentProcessingFailedError(
            "Document processing failed",
            code="processing_failed",
        ) from exc

    try:
        replace_document_chunks(
            db,
            document_id=snapshot.document_id,
            chunks=chunking.chunks,
        )
        db.execute(
            update(Document)
            .where(Document.id == snapshot.document_id)
            .values(status=DocumentStatus.PROCESSED)
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(
            "Document chunk persistence failed document_id=%s",
            snapshot.document_id,
        )
        _mark_failed(db, snapshot.document_id)
        db.commit()
        raise DocumentProcessingFailedError(
            "Failed to persist document chunks",
            code="persistence_failed",
        ) from None

    chunk_count = len(chunking.chunks)
    return DocumentProcessResult(
        document_id=snapshot.document_id,
        status=DocumentStatus.PROCESSED,
        chunk_count=chunk_count,
    )


def _extract_and_chunk(
    snapshot: _DocumentProcessingSnapshot,
    storage: LocalDocumentStorage,
):
    file_bytes = _load_verified_bytes(snapshot, storage)
    extraction = extract_document_text(
        file_bytes,
        filename=snapshot.original_filename,
    )
    if extraction.truncated:
        raise DocumentProcessingFailedError(
            "Extracted text exceeded configured limits",
            code="extraction_truncated",
        )
    if not extraction.text.strip() and not any(
        page.text.strip() for page in extraction.pages
    ):
        raise DocumentProcessingFailedError(
            "No extractable text in document",
            code="empty_extraction",
        )
    chunking = chunk_extraction_result(extraction)
    if not chunking.chunks:
        raise DocumentProcessingFailedError(
            "Chunking produced no usable chunks",
            code="empty_chunks",
        )
    return chunking


def _claim_for_processing(
    session: Session,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
) -> bool:
    result = session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.collection_id == collection_id,
            Document.status.in_(_ELIGIBLE_FOR_PROCESSING),
        )
        .values(status=DocumentStatus.PROCESSING)
        .returning(Document.id)
    )
    return result.first() is not None


def _raise_claim_conflict(
    session: Session,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
) -> None:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    if document is None:
        raise DocumentProcessingFailedError(
            "Document not found",
            code="not_found",
        )
    if document.status == DocumentStatus.PROCESSING:
        raise DocumentProcessingConflictError("Document is already being processed")
    if document.status == DocumentStatus.READY:
        raise DocumentProcessingConflictError(
            "Document is ready for indexing; reprocessing is not allowed yet"
        )
    raise DocumentProcessingConflictError(
        "Document cannot be processed in its current state"
    )


def _load_verified_bytes(
    snapshot: _DocumentProcessingSnapshot,
    storage: LocalDocumentStorage,
) -> bytes:
    data = storage.read(snapshot.storage_key)
    if len(data) != snapshot.size_bytes:
        raise DocumentProcessingFailedError(
            "Stored file size does not match document metadata",
            code="storage_integrity",
        )
    if snapshot.content_hash_sha256:
        digest = hashlib.sha256(data).hexdigest()
        if digest != snapshot.content_hash_sha256:
            raise DocumentProcessingFailedError(
                "Stored file hash does not match document metadata",
                code="storage_integrity",
            )
    return data


def _mark_failed(session: Session, document_id: uuid.UUID) -> None:
    session.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=DocumentStatus.FAILED)
    )


def count_document_chunks(session: Session, document_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        or 0
    )
