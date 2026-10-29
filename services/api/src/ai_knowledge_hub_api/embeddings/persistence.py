"""Persist chunk embeddings to PostgreSQL (caller owns the transaction)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.service import validate_embedding_vector
from ai_knowledge_hub_api.models.document import Document, DocumentStatus
from ai_knowledge_hub_api.models.document_chunk import DocumentChunk

DEFAULT_EMBEDDING_CONFIG = EmbeddingConfig()

_EMBEDDING_PERSIST_STATUSES = frozenset(
    {
        DocumentStatus.PROCESSED,
        DocumentStatus.INDEXING,
    }
)


class ChunkEmbeddingPersistenceError(Exception):
    """Invalid embedding payload or document state for persistence."""


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingInput:
    chunk_index: int
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class StoredChunkEmbedding:
    chunk_index: int
    vector: tuple[float, ...]
    embedding_model: str
    embedded_at: datetime


def persist_document_chunk_embeddings(
    session: Session,
    *,
    document_id: uuid.UUID,
    embeddings: Sequence[ChunkEmbeddingInput],
    embedding_model: str,
    embedded_at: datetime | None = None,
    config: EmbeddingConfig | None = None,
) -> None:
    """
    Atomically attach embeddings to existing chunks within the caller's transaction.

    Validates all inputs before updating any row. On rollback, prior embeddings
    remain unchanged.
    """
    resolved = config or DEFAULT_EMBEDDING_CONFIG
    _validate_embedding_model(embedding_model, resolved)
    stamp = embedded_at or datetime.now(UTC)

    document = session.scalar(
        select(Document).where(Document.id == document_id).with_for_update()
    )
    if document is None:
        raise ChunkEmbeddingPersistenceError("Document not found")
    if document.status not in _EMBEDDING_PERSIST_STATUSES:
        raise ChunkEmbeddingPersistenceError(
            "Embeddings may only be stored for documents in "
            "PROCESSED or INDEXING status"
        )

    rows = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .with_for_update()
    ).all()

    expected_indices = {row.chunk_index for row in rows}
    if not expected_indices and embeddings:
        raise ChunkEmbeddingPersistenceError(
            "Document has no chunks; cannot persist embeddings"
        )

    provided_indices = [item.chunk_index for item in embeddings]
    if len(provided_indices) != len(set(provided_indices)):
        raise ChunkEmbeddingPersistenceError("Duplicate chunk_index in embedding batch")
    provided_set = set(provided_indices)
    if provided_set != expected_indices:
        missing = sorted(expected_indices - provided_set)
        unexpected = sorted(provided_set - expected_indices)
        parts: list[str] = []
        if missing:
            parts.append(f"missing indices: {missing}")
        if unexpected:
            parts.append(f"unexpected indices: {unexpected}")
        raise ChunkEmbeddingPersistenceError(
            "Embedding indices must exactly match document chunks"
            + (f" ({'; '.join(parts)})" if parts else "")
        )

    by_index = {item.chunk_index: item for item in embeddings}
    for row in rows:
        item = by_index[row.chunk_index]
        validate_embedding_vector(
            item.vector,
            expected_dimensions=resolved.expected_dimensions,
        )

    for row in rows:
        item = by_index[row.chunk_index]
        row.embedding = list(item.vector)
        row.embedding_model = embedding_model
        row.embedded_at = stamp

    session.flush()


def load_document_chunk_embeddings(
    session: Session,
    document_id: uuid.UUID,
) -> tuple[StoredChunkEmbedding, ...]:
    rows = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    stored: list[StoredChunkEmbedding] = []
    for row in rows:
        if row.embedding is None:
            continue
        if row.embedding_model is None or row.embedded_at is None:
            raise ChunkEmbeddingPersistenceError(
                "Chunk has embedding vector but incomplete metadata"
            )
        stored.append(
            StoredChunkEmbedding(
                chunk_index=row.chunk_index,
                vector=tuple(float(value) for value in row.embedding),
                embedding_model=row.embedding_model,
                embedded_at=row.embedded_at,
            )
        )
    return tuple(stored)


def _validate_embedding_model(
    embedding_model: str,
    config: EmbeddingConfig,
) -> None:
    if not embedding_model or not embedding_model.strip():
        raise ChunkEmbeddingPersistenceError("embedding_model must be non-empty")
    if embedding_model != config.model_name:
        raise ChunkEmbeddingPersistenceError(
            f"embedding_model must be {config.model_name!r}, got {embedding_model!r}"
        )
