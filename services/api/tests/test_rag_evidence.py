"""Unit tests for RAG evidence context building."""

import uuid

from ai_knowledge_hub_api.rag.config import RagConfig
from ai_knowledge_hub_api.rag.evidence import build_evidence_context
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


def _match(
    *,
    doc: uuid.UUID,
    chunk_index: int,
    text: str,
    filename: str = "doc.txt",
) -> SemanticSearchMatch:
    return SemanticSearchMatch(
        document_id=doc,
        original_filename=filename,
        chunk_index=chunk_index,
        text=text,
        source_kind="text",
        page_numbers=(chunk_index + 1,),
        cosine_distance=0.1,
    )


def test_build_evidence_deduplicates_same_chunk() -> None:
    doc_id = uuid.uuid4()
    row = _match(doc=doc_id, chunk_index=0, text="hello world")
    sources = build_evidence_context(
        [row, row],
        config=RagConfig(max_evidence_passages=5, max_evidence_characters=1000),
    )
    assert len(sources) == 1
    assert sources[0].source_id == "S1"


def test_build_evidence_respects_passage_and_character_limits() -> None:
    doc_id = uuid.uuid4()
    matches = [
        _match(doc=doc_id, chunk_index=0, text="a" * 40),
        _match(doc=doc_id, chunk_index=1, text="b" * 40),
        _match(doc=doc_id, chunk_index=2, text="c" * 40),
    ]
    sources = build_evidence_context(
        matches,
        config=RagConfig(max_evidence_passages=2, max_evidence_characters=100),
    )
    assert len(sources) == 2
    assert sources[0].source_id == "S1"
    assert sources[1].source_id == "S2"


def test_build_evidence_skips_oversized_first_chunk_without_truncation() -> None:
    doc_id = uuid.uuid4()
    matches = [_match(doc=doc_id, chunk_index=0, text="x" * 500)]
    sources = build_evidence_context(
        matches,
        config=RagConfig(max_evidence_passages=3, max_evidence_characters=100),
    )
    assert sources == []
