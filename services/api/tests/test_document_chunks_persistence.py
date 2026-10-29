"""Unit tests for chunk persistence helpers."""

import pytest

from ai_knowledge_hub_api.documents.chunking.types import TextChunk
from ai_knowledge_hub_api.documents.chunks.persistence import (
    ChunkPersistenceError,
    _validate_chunks,
)


def test_validate_chunks_rejects_duplicate_index() -> None:
    chunks = (
        TextChunk(0, "a", "text", (1,), 1),
        TextChunk(0, "b", "text", (1,), 1),
    )
    with pytest.raises(ChunkPersistenceError, match="unique"):
        _validate_chunks(chunks)


def test_validate_chunks_rejects_empty_text() -> None:
    chunks = (TextChunk(0, "   ", "text", (1,), 3),)
    with pytest.raises(ChunkPersistenceError, match="non-empty"):
        _validate_chunks(chunks)
