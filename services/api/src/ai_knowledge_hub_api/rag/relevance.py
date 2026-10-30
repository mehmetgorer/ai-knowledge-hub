"""Retrieval strength heuristics (optional pre-generation abstention)."""

from ai_knowledge_hub_api.rag.evidence import EvidenceSource


def best_evidence_cosine_distance(evidence: list[EvidenceSource]) -> float | None:
    if not evidence:
        return None
    return min(item.match.cosine_distance for item in evidence)


def should_abstain_for_weak_retrieval(
    evidence: list[EvidenceSource],
    *,
    weak_best_distance_above: float | None,
) -> bool:
    """
    When configured, skip LLM generation if the closest passage is still very
    distant. Disabled by default (threshold None) because multilingual E5 can
    rank relevant cross-language passages with moderate distances.
    """
    if weak_best_distance_above is None:
        return False
    best = best_evidence_cosine_distance(evidence)
    if best is None:
        return True
    return best > weak_best_distance_above
