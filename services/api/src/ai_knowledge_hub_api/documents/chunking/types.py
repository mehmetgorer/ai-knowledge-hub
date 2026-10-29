from dataclasses import dataclass

from ai_knowledge_hub_api.documents.extraction.types import SourceKind


@dataclass(frozen=True)
class ChunkingConfig:
    """
    Character-based chunk sizing (not embedding token counts).

    target_characters: preferred size before starting a new chunk.
    max_characters: hard upper bound per chunk body.
    overlap_characters: suffix of the previous chunk repeated at the next chunk start.
    max_chunks: maximum chunks allowed; exceeding raises ChunkingLimitExceededError.
    """

    target_characters: int = 1000
    max_characters: int = 1500
    overlap_characters: int = 100
    max_chunks: int = 10_000


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    source_kind: SourceKind
    page_numbers: tuple[int, ...]
    character_count: int


@dataclass(frozen=True)
class ChunkingResult:
    chunks: tuple[TextChunk, ...]
    source_character_count: int
