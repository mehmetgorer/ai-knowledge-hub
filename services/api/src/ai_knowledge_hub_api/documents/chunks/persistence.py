"""Persist chunking results to PostgreSQL (caller owns the transaction)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.documents.chunking.types import TextChunk
from ai_knowledge_hub_api.models.document_chunk import DocumentChunk


class ChunkPersistenceError(Exception):
    """Invalid chunk payload for persistence."""


def load_document_chunks(
    session: Session,
    document_id: uuid.UUID,
) -> tuple[TextChunk, ...]:
    rows = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    return tuple(_row_to_text_chunk(row) for row in rows)


def replace_document_chunks(
    session: Session,
    *,
    document_id: uuid.UUID,
    chunks: Sequence[TextChunk],
) -> None:
    """
    Atomically replace all chunks for a document within the caller's transaction.

    On commit, only the new rows remain. On rollback after this call, prior rows
    are restored and partial replacements are not visible.
    """
    _validate_chunks(chunks)
    session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    for chunk in chunks:
        session.add(_text_chunk_to_row(document_id, chunk))
    session.flush()


def _validate_chunks(chunks: Sequence[TextChunk]) -> None:
    indices = [chunk.chunk_index for chunk in chunks]
    if len(indices) != len(set(indices)):
        raise ChunkPersistenceError("chunk_index values must be unique within a batch")
    for chunk in chunks:
        if chunk.character_count != len(chunk.text):
            raise ChunkPersistenceError(
                "character_count must match len(text) for each chunk"
            )
        if not chunk.text.strip():
            raise ChunkPersistenceError("chunk text must be non-empty")


def _text_chunk_to_row(document_id: uuid.UUID, chunk: TextChunk) -> DocumentChunk:
    return DocumentChunk(
        document_id=document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        source_kind=chunk.source_kind,
        page_numbers=list(chunk.page_numbers),
        character_count=chunk.character_count,
    )


def _row_to_text_chunk(row: DocumentChunk) -> TextChunk:
    return TextChunk(
        chunk_index=row.chunk_index,
        text=row.text,
        source_kind=row.source_kind,  # type: ignore[arg-type]
        page_numbers=tuple(row.page_numbers),
        character_count=row.character_count,
    )
