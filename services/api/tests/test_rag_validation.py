"""Unit tests for grounded answer validation."""

import json
import uuid

import pytest

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import RagGroundingError, RagOllamaResponseError
from ai_knowledge_hub_api.rag.evidence import EvidenceSource
from ai_knowledge_hub_api.rag.parse_completion import parse_structured_completion
from ai_knowledge_hub_api.rag.service import apply_validated_answer_for_tests
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


def _evidence(text: str = "SQL JOIN combines rows.") -> list[EvidenceSource]:
    match = SemanticSearchMatch(
        document_id=uuid.uuid4(),
        original_filename="database.txt",
        chunk_index=0,
        text=text,
        source_kind="text",
        page_numbers=(1,),
        cosine_distance=0.16,
    )
    return [EvidenceSource(source_id="S1", match=match)]


def test_validates_grounded_answer_with_matching_citations() -> None:
    passage = "SQL JOIN combines rows from tables."
    payload = {
        "answer": "A JOIN combines rows from tables [S1].",
        "cited_source_ids": ["S1"],
        "evidence_sufficient": True,
        "support_quotes": [
            {"source_id": "S1", "quote": "SQL JOIN combines rows"},
        ],
    }
    validated = apply_validated_answer_for_tests(payload, _evidence(passage))
    assert validated.grounded is True
    assert validated.cited_source_ids == ("S1",)


def test_rejects_invented_citation_ids() -> None:
    payload = {
        "answer": "See [S9] for details.",
        "cited_source_ids": ["S9"],
        "evidence_sufficient": True,
        "support_quotes": [{"source_id": "S9", "quote": "fabricated quote text"}],
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_allows_insufficient_evidence_without_citations() -> None:
    payload = {
        "answer": "The evidence does not contain enough information.",
        "cited_source_ids": [],
        "evidence_sufficient": False,
        "support_quotes": [],
    }
    validated = apply_validated_answer_for_tests(payload, _evidence())
    assert validated.grounded is False
    assert validated.cited_source_ids == ()


def test_rejects_answer_with_inline_citation_not_listed() -> None:
    payload = {
        "answer": "Details in [S1].",
        "cited_source_ids": [],
        "evidence_sufficient": False,
        "support_quotes": [],
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_parse_structured_completion_rejects_non_json() -> None:
    with pytest.raises(RagOllamaResponseError):
        parse_structured_completion("not json")


def test_parse_structured_completion_parses_json_object() -> None:
    payload = parse_structured_completion(
        json.dumps(
            {
                "answer": "ok",
                "cited_source_ids": [],
                "evidence_sufficient": False,
                "support_quotes": [],
            },
        ),
    )
    assert payload["answer"] == "ok"


def test_rejects_citations_when_evidence_insufficient() -> None:
    payload = {
        "answer": "Maybe [S1].",
        "cited_source_ids": ["S1"],
        "evidence_sufficient": False,
        "support_quotes": [],
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_requires_evidence_sufficient_flag() -> None:
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            {"answer": "x", "cited_source_ids": [], "support_quotes": []},
            _evidence(),
        )
    assert exc_info.value.code == codes.MISSING_EVIDENCE_SUFFICIENT


def test_normalizes_missing_inline_citations_when_other_checks_pass() -> None:
    passage = "SQL JOIN combines rows from tables."
    payload = {
        "answer": "A JOIN combines rows from tables.",
        "cited_source_ids": ["S1"],
        "evidence_sufficient": True,
        "support_quotes": [
            {"source_id": "S1", "quote": "SQL JOIN combines rows"},
        ],
    }
    validated = apply_validated_answer_for_tests(payload, _evidence(passage))
    assert validated.grounded is True
    assert "[S1]" in validated.answer
