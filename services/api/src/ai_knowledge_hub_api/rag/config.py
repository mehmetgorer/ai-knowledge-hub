"""RAG pipeline limits (injectable; not user-controlled per request)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RagConfig:
    max_evidence_passages: int = 5
    max_evidence_characters: int = 12_000
    max_output_tokens: int = 512
    weak_retrieval_best_distance_above: float | None = None
