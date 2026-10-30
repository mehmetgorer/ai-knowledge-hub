"""Calibration notes for optional cosine-distance abstention (disabled by default)."""

import uuid

from ai_knowledge_hub_api.rag.evidence import EvidenceSource
from ai_knowledge_hub_api.rag.relevance import should_abstain_for_weak_retrieval
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


def _source(distance: float) -> EvidenceSource:
    return EvidenceSource(
        source_id="S1",
        match=SemanticSearchMatch(
            document_id=uuid.uuid4(),
            original_filename="doc.txt",
            chunk_index=0,
            text="passage",
            source_kind="text",
            page_numbers=(1,),
            cosine_distance=distance,
        ),
    )


def test_positive_match_not_abstained_at_conservative_threshold() -> None:
    evidence = [_source(0.16)]
    assert (
        should_abstain_for_weak_retrieval(
            evidence,
            weak_best_distance_above=0.85,
        )
        is False
    )


def test_unrelated_high_distance_abstained_when_threshold_enabled() -> None:
    evidence = [_source(0.94)]
    assert (
        should_abstain_for_weak_retrieval(
            evidence,
            weak_best_distance_above=0.85,
        )
        is True
    )


def test_borderline_cross_language_not_abstained_at_conservative_threshold() -> None:
    """Relevant TR question / EN chunk can sit near ~0.45 on E5 — not filtered."""
    evidence = [_source(0.45)]
    assert (
        should_abstain_for_weak_retrieval(
            evidence,
            weak_best_distance_above=0.85,
        )
        is False
    )


def test_aggressive_threshold_would_drop_borderline_cross_language() -> None:
    evidence = [_source(0.45)]
    assert (
        should_abstain_for_weak_retrieval(
            evidence,
            weak_best_distance_above=0.35,
        )
        is True
    )


def test_disabled_threshold_never_abstains() -> None:
    evidence = [_source(0.99)]
    assert (
        should_abstain_for_weak_retrieval(
            evidence,
            weak_best_distance_above=None,
        )
        is False
    )
