"""Unit tests for grounded answer validation."""

import json
import uuid

import pytest

from ai_knowledge_hub_api.rag.errors import RagGroundingError
from ai_knowledge_hub_api.rag.evidence import EvidenceSource
from ai_knowledge_hub_api.rag.service import apply_validated_answer_for_tests
from ai_knowledge_hub_api.rag.validation import parse_structured_completion
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
    payload = {
        "answer": "A JOIN combines rows from tables [S1].",
        "cited_source_ids": ["S1"],
        "evidence_sufficient": True,
    }
    validated = apply_validated_answer_for_tests(payload, _evidence())
    assert validated.grounded is True
    assert validated.cited_source_ids == ("S1",)


def test_rejects_invented_citation_ids() -> None:
    payload = {
        "answer": "See [S9] for details.",
        "cited_source_ids": ["S9"],
        "evidence_sufficient": True,
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_allows_insufficient_evidence_without_citations() -> None:
    payload = {
        "answer": "The evidence does not contain enough information.",
        "cited_source_ids": [],
        "evidence_sufficient": False,
    }
    validated = apply_validated_answer_for_tests(payload, _evidence())
    assert validated.grounded is False
    assert validated.cited_source_ids == ()


def test_rejects_answer_with_inline_citation_not_listed() -> None:
    payload = {
        "answer": "Details in [S1].",
        "cited_source_ids": [],
        "evidence_sufficient": False,
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_parse_structured_completion_rejects_non_json() -> None:
    with pytest.raises(Exception):
        parse_structured_completion("not json")


def test_parse_structured_completion_parses_json_object() -> None:
    payload = parse_structured_completion(
        json.dumps(
            {
                "answer": "ok",
                "cited_source_ids": [],
                "evidence_sufficient": False,
            },
        ),
    )
    assert payload["answer"] == "ok"


def test_rejects_citations_when_evidence_insufficient() -> None:
    payload = {
        "answer": "Maybe [S1].",
        "cited_source_ids": ["S1"],
        "evidence_sufficient": False,
    }
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(payload, _evidence())


def test_requires_evidence_sufficient_flag() -> None:
    with pytest.raises(RagGroundingError):
        apply_validated_answer_for_tests(
            {"answer": "x", "cited_source_ids": []},
            _evidence(),
        )
