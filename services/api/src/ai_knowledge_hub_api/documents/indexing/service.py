"""On-demand document chunk embedding / indexing pipeline."""

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import EmbeddingError
from ai_knowledge_hub_api.embeddings.persistence import (
    ChunkEmbeddingInput,
    ChunkEmbeddingPersistenceError,
    persist_document_chunk_embeddings,
)
from ai_knowledge_hub_api.embeddings.service import (
    DEFAULT_EMBEDDING_CONFIG,
    embed_document_chunks,
)
from ai_knowledge_hub_api.models import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentIndexingConflictError(Exception):
    """Document cannot be claimed for indexing (concurrency or status)."""


class DocumentIndexingFailedError(Exception):
    """Embedding inference or persistence failed."""

    def __init__(self, message: str, *, code: str = "indexing_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class DocumentIndexResult:
    document_id: uuid.UUID
    status: DocumentStatus
    embedding_model: str
    embedded_chunk_count: int


@dataclass(frozen=True)
class _DocumentIndexSnapshot:
    document_id: uuid.UUID
    collection_id: uuid.UUID


@dataclass(frozen=True)
class _ChunkTextSnapshot:
    chunk_index: int
    text: str


EmbedChunksFn = Callable[[Sequence[str], EmbeddingConfig], list[list[float]]]


def index_document(
    db: Session,
    *,
    document: Document,
    config: EmbeddingConfig | None = None,
    embed_chunks: EmbedChunksFn | None = None,
) -> DocumentIndexResult:
    """
    Claim PROCESSED → INDEXING, embed off-connection, persist vectors, mark READY.

    Commits status transitions. On failure restores PROCESSED without removing chunks.
    """
    resolved = config or DEFAULT_EMBEDDING_CONFIG
    embed_fn = embed_chunks or _default_embed_chunks
    snapshot = _DocumentIndexSnapshot(
        document_id=document.id,
        collection_id=document.collection_id,
    )

    if not _claim_for_indexing(db, snapshot.document_id, snapshot.collection_id):
        db.rollback()
        _raise_claim_conflict(db, snapshot.document_id, snapshot.collection_id)
    db.commit()

    try:
        chunk_rows = _load_chunk_texts(db, snapshot.document_id)
        db.commit()
    except Exception:
        db.rollback()
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Failed to load document chunks",
            code="chunk_load_failed",
        ) from None

    if not chunk_rows:
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Document has no chunks to index",
            code="empty_chunks",
        )

    texts = [row.text for row in chunk_rows]
    try:
        vectors = embed_fn(texts, resolved)
    except EmbeddingError as exc:
        logger.warning(
            "Document indexing embedding failed document_id=%s code=%s",
            snapshot.document_id,
            getattr(exc, "code", type(exc).__name__),
        )
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Embedding generation failed",
            code=getattr(exc, "code", "indexing_failed"),
        ) from exc
    except Exception as exc:
        logger.warning(
            "Document indexing embedding failed document_id=%s error_type=%s",
            snapshot.document_id,
            type(exc).__name__,
        )
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Embedding generation failed",
            code="indexing_failed",
        ) from exc

    if len(vectors) != len(chunk_rows):
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Embedding output count mismatch",
            code="indexing_failed",
        )

    embeddings = tuple(
        ChunkEmbeddingInput(
            chunk_index=chunk_rows[index].chunk_index,
            vector=tuple(vectors[index]),
        )
        for index in range(len(chunk_rows))
    )

    try:
        persist_document_chunk_embeddings(
            db,
            document_id=snapshot.document_id,
            embeddings=embeddings,
            embedding_model=resolved.model_name,
            config=resolved,
        )
        db.execute(
            update(Document)
            .where(Document.id == snapshot.document_id)
            .values(status=DocumentStatus.READY)
        )
        db.commit()
    except (ChunkEmbeddingPersistenceError, Exception):
        db.rollback()
        logger.warning(
            "Document embedding persistence failed document_id=%s",
            snapshot.document_id,
        )
        _restore_processed(db, snapshot.document_id)
        db.commit()
        raise DocumentIndexingFailedError(
            "Failed to persist document embeddings",
            code="persistence_failed",
        ) from None

    return DocumentIndexResult(
        document_id=snapshot.document_id,
        status=DocumentStatus.READY,
        embedding_model=resolved.model_name,
        embedded_chunk_count=len(embeddings),
    )


def _default_embed_chunks(
    texts: Sequence[str],
    config: EmbeddingConfig,
) -> list[list[float]]:
    return embed_document_chunks(texts, config=config)


def _claim_for_indexing(
    session: Session,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
) -> bool:
    result = session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.collection_id == collection_id,
            Document.status == DocumentStatus.PROCESSED,
        )
        .values(status=DocumentStatus.INDEXING)
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
        raise DocumentIndexingFailedError(
            "Document not found",
            code="not_found",
        )
    if document.status == DocumentStatus.INDEXING:
        raise DocumentIndexingConflictError("Document is already being indexed")
    if document.status == DocumentStatus.PROCESSING:
        raise DocumentIndexingConflictError("Document is being processed")
    if document.status == DocumentStatus.READY:
        raise DocumentIndexingConflictError("Document is already indexed")
    raise DocumentIndexingConflictError(
        "Document cannot be indexed in its current state"
    )


def _load_chunk_texts(
    session: Session,
    document_id: uuid.UUID,
) -> tuple[_ChunkTextSnapshot, ...]:
    rows = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    return tuple(
        _ChunkTextSnapshot(chunk_index=row.chunk_index, text=row.text) for row in rows
    )


def _restore_processed(session: Session, document_id: uuid.UUID) -> None:
    session.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=DocumentStatus.PROCESSED)
    )
