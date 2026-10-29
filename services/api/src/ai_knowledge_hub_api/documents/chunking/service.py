from ai_knowledge_hub_api.documents.chunking.errors import (
    ChunkingConfigurationError,
    ChunkingLimitExceededError,
)
from ai_knowledge_hub_api.documents.chunking.segments import (
    split_markdown_units,
    split_oversized_unit,
    split_plain_units,
)
from ai_knowledge_hub_api.documents.chunking.types import (
    ChunkingConfig,
    ChunkingResult,
    TextChunk,
)
from ai_knowledge_hub_api.documents.extraction.types import ExtractionResult, SourceKind

_UNIT_SEPARATOR = "\n\n"


def validate_chunking_config(config: ChunkingConfig) -> None:
    if config.target_characters < 1:
        raise ChunkingConfigurationError("target_characters must be at least 1")
    if config.max_characters < 1:
        raise ChunkingConfigurationError("max_characters must be at least 1")
    if config.target_characters > config.max_characters:
        raise ChunkingConfigurationError(
            "target_characters must not exceed max_characters"
        )
    if config.overlap_characters < 0:
        raise ChunkingConfigurationError("overlap_characters must be non-negative")
    if config.overlap_characters >= config.max_characters:
        raise ChunkingConfigurationError(
            "overlap_characters must be smaller than max_characters"
        )
    if config.max_chunks < 1:
        raise ChunkingConfigurationError("max_chunks must be at least 1")


def chunk_extraction_result(
    extraction: ExtractionResult,
    *,
    config: ChunkingConfig | None = None,
) -> ChunkingResult:
    """
    Split extracted document text into deterministic, structure-aware chunks.

    Character counts are not embedding token counts.
    """
    resolved = config or ChunkingConfig()
    validate_chunking_config(resolved)

    chunks: list[TextChunk] = []
    next_index = 0
    source_character_count = 0

    if extraction.source_kind == "pdf":
        for page in extraction.pages:
            page_text = page.text.strip()
            if not page_text:
                continue
            source_character_count += len(page_text)
            next_index = _chunk_page_text(
                page_text,
                source_kind="pdf",
                page_number=page.page_number,
                config=resolved,
                chunks=chunks,
                next_index=next_index,
            )
    else:
        body = extraction.text.strip()
        if not body:
            return ChunkingResult(chunks=tuple(), source_character_count=0)
        source_character_count = len(body)
        page_number = extraction.pages[0].page_number if extraction.pages else 1
        next_index = _chunk_page_text(
            body,
            source_kind=extraction.source_kind,
            page_number=page_number,
            config=resolved,
            chunks=chunks,
            next_index=next_index,
            markdown=extraction.source_kind == "markdown",
        )

    return ChunkingResult(
        chunks=tuple(chunks),
        source_character_count=source_character_count,
    )


def _compose_chunk_text(parts: list[str]) -> str:
    return _UNIT_SEPARATOR.join(parts).strip()


def _trim_overlap_for_unit(
    overlap_prefix: str,
    unit: str,
    *,
    max_characters: int,
) -> str:
    if not overlap_prefix:
        return ""
    max_overlap_len = max_characters - len(unit) - len(_UNIT_SEPARATOR)
    if max_overlap_len <= 0:
        return ""
    if len(overlap_prefix) <= max_overlap_len:
        return overlap_prefix
    return overlap_prefix[-max_overlap_len:]


def _begin_next_buffer(
    overlap_prefix: str,
    unit: str,
    *,
    max_characters: int,
) -> list[str]:
    if not overlap_prefix:
        return [unit]

    combined = _compose_chunk_text([overlap_prefix, unit])
    if len(combined) <= max_characters:
        return [overlap_prefix, unit]

    reduced = _trim_overlap_for_unit(
        overlap_prefix,
        unit,
        max_characters=max_characters,
    )
    if reduced:
        combined = _compose_chunk_text([reduced, unit])
        if len(combined) <= max_characters:
            return [reduced, unit]
    return [unit]


def _chunk_page_text(
    text: str,
    *,
    source_kind: SourceKind,
    page_number: int,
    config: ChunkingConfig,
    chunks: list[TextChunk],
    next_index: int,
    markdown: bool = False,
) -> int:
    units = split_markdown_units(text) if markdown else split_plain_units(text)
    expanded: list[str] = []
    for unit in units:
        expanded.extend(
            split_oversized_unit(unit, max_characters=config.max_characters)
        )

    if not expanded:
        return next_index

    buffer_parts: list[str] = []
    pending_overlap = ""

    def append_chunk(parts: list[str]) -> str:
        nonlocal next_index
        chunk_text = _compose_chunk_text(parts)
        if not chunk_text:
            return ""
        if len(chunk_text) > config.max_characters:
            raise ChunkingConfigurationError(
                "Internal chunking error: chunk exceeds max_characters"
            )
        if len(chunks) >= config.max_chunks:
            raise ChunkingLimitExceededError(
                "Document exceeds configured max_chunks before processing completed"
            )
        chunks.append(
            TextChunk(
                chunk_index=next_index,
                text=chunk_text,
                source_kind=source_kind,
                page_numbers=(page_number,),
                character_count=len(chunk_text),
            )
        )
        next_index += 1
        return _overlap_suffix(chunk_text, config.overlap_characters)

    def enforce_max_on_buffer() -> None:
        nonlocal buffer_parts, pending_overlap
        while buffer_parts:
            text = _compose_chunk_text(buffer_parts)
            if len(text) <= config.max_characters:
                return
            if len(buffer_parts) == 1:
                raise ChunkingConfigurationError(
                    "A single unit exceeds max_characters even after splitting"
                )
            pending_overlap = append_chunk(buffer_parts[:-1])
            buffer_parts = _begin_next_buffer(
                pending_overlap,
                buffer_parts[-1],
                max_characters=config.max_characters,
            )

    for unit in expanded:
        if len(unit) > config.max_characters:
            raise ChunkingConfigurationError(
                "A single unit exceeds max_characters even after splitting"
            )

        if pending_overlap and not buffer_parts:
            buffer_parts = _begin_next_buffer(
                pending_overlap,
                unit,
                max_characters=config.max_characters,
            )
            pending_overlap = ""
        elif not buffer_parts:
            buffer_parts = [unit]
        else:
            trial_parts = buffer_parts + [unit]
            trial_text = _compose_chunk_text(trial_parts)
            if len(trial_text) <= config.max_characters:
                buffer_parts = trial_parts
            else:
                pending_overlap = append_chunk(buffer_parts)
                buffer_parts = _begin_next_buffer(
                    pending_overlap,
                    unit,
                    max_characters=config.max_characters,
                )
                pending_overlap = ""

        enforce_max_on_buffer()

        buffer_text = _compose_chunk_text(buffer_parts)
        if len(buffer_text) > config.target_characters and len(buffer_parts) > 1:
            pending_overlap = append_chunk(buffer_parts[:-1])
            buffer_parts = _begin_next_buffer(
                pending_overlap,
                buffer_parts[-1],
                max_characters=config.max_characters,
            )
            enforce_max_on_buffer()

    if buffer_parts:
        append_chunk(buffer_parts)

    return next_index


def _overlap_suffix(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    if len(text) <= overlap:
        return text
    tail = text[-overlap:]
    for separator in ("\n\n", "\n", ". ", " "):
        position = tail.find(separator)
        if position != -1:
            return tail[position + len(separator) :]
    return tail


def collect_chunk_units_for_coverage(
    extraction: ExtractionResult,
) -> list[str]:
    """Expand extraction text into chunking units (for test coverage checks)."""
    units: list[str] = []
    if extraction.source_kind == "pdf":
        for page in extraction.pages:
            page_text = page.text.strip()
            if not page_text:
                continue
            for unit in split_plain_units(page_text):
                units.extend(split_oversized_unit(unit, max_characters=10**9))
    else:
        body = extraction.text.strip()
        if not body:
            return []
        base = (
            split_markdown_units(body)
            if extraction.source_kind == "markdown"
            else split_plain_units(body)
        )
        for unit in base:
            units.extend(split_oversized_unit(unit, max_characters=10**9))
    return units
