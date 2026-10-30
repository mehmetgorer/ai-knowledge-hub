"""Unit tests for ask outcome classification."""

from ai_knowledge_hub_api.rag.outcome import AskGenerationOutcomeKind


def test_outcome_kind_values() -> None:
    assert AskGenerationOutcomeKind.GROUNDED == "grounded"
    assert AskGenerationOutcomeKind.SAFE_ABSTENTION == "safe_abstention"
