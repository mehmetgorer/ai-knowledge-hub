"""RAG /ask generation outcome classification (API-facing)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_knowledge_hub_api.rag.service import AskCollectionResult


class AskGenerationOutcomeKind(StrEnum):
    """How the ask pipeline resolved after retrieval + optional LLM."""

    GROUNDED = "grounded"
    SAFE_ABSTENTION = "safe_abstention"


@dataclass(frozen=True, slots=True)
class AskGenerationOutcome:
    kind: AskGenerationOutcomeKind
    result: "AskCollectionResult"
