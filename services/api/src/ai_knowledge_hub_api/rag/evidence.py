"""Build bounded, deduplicated evidence blocks with deterministic source IDs."""

from dataclasses import dataclass

from ai_knowledge_hub_api.rag.config import RagConfig
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    match: SemanticSearchMatch


def build_evidence_context(
    matches: list[SemanticSearchMatch],
    *,
    config: RagConfig,
) -> list[EvidenceSource]:
    """Include whole passages only; drop trailing chunks when over the char budget."""
    seen: set[tuple[object, int]] = set()
    sources: list[EvidenceSource] = []
    total_chars = 0

    for match in matches:
        key = (match.document_id, match.chunk_index)
        if key in seen:
            continue
        seen.add(key)

        if len(sources) >= config.max_evidence_passages:
            break

        passage = match.text
        passage_len = len(passage)
        if not passage.strip():
            continue

        if sources and total_chars + passage_len > config.max_evidence_characters:
            break

        if not sources and passage_len > config.max_evidence_characters:
            break

        source_id = f"S{len(sources) + 1}"
        sources.append(EvidenceSource(source_id=source_id, match=match))
        total_chars += passage_len

    return sources


def format_evidence_block(sources: list[EvidenceSource]) -> str:
    lines: list[str] = []
    for item in sources:
        pages = ", ".join(str(value) for value in item.match.page_numbers) or "—"
        lines.append(
            f"[{item.source_id}] file={item.match.original_filename!r} "
            f"chunk={item.match.chunk_index} pages={pages}\n"
            f"{item.match.text}"
        )
    return "\n\n".join(lines)
