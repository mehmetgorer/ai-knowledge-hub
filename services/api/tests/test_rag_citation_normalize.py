"""Regression tests for deterministic inline citation normalization."""

import json
import uuid

import pytest

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.citation_format import append_missing_inline_citations
from ai_knowledge_hub_api.rag.errors import RagGroundingError
from ai_knowledge_hub_api.rag.evidence import EvidenceSource
from ai_knowledge_hub_api.rag.generation import complete_and_validate_grounded_answer
from ai_knowledge_hub_api.rag.ollama import OllamaChatRequest
from ai_knowledge_hub_api.rag.service import apply_validated_answer_for_tests
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


def _evidence(*texts: str) -> list[EvidenceSource]:
    result: list[EvidenceSource] = []
    for index, text in enumerate(texts, start=1):
        match = SemanticSearchMatch(
            document_id=uuid.uuid4(),
            original_filename="rag-test.pdf",
            chunk_index=index - 1,
            text=text,
            source_kind="text",
            page_numbers=(index,),
            cosine_distance=0.14,
        )
        result.append(EvidenceSource(source_id=f"S{index}", match=match))
    return result


def _grounded_payload(
    *,
    answer: str,
    cited: list[str],
    quotes: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "answer": answer,
        "cited_source_ids": cited,
        "evidence_sufficient": True,
        "support_quotes": quotes,
    }


def test_pdf_style_answer_missing_inline_normalized_to_grounded() -> None:
    passage = "Projede backend olarak FastAPI kullanılmaktadır."
    payload = _grounded_payload(
        answer="Backend teknolojisi FastAPI olarak seçilmiştir.",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "FastAPI kullanılmaktadır"}],
    )
    validated = apply_validated_answer_for_tests(
        payload,
        _evidence(passage),
        question="Projede hangi backend teknolojisi kullanılıyor?",
    )
    assert validated.grounded is True
    assert validated.cited_source_ids == ("S1",)
    assert "[S1]" in validated.answer
    assert "FastAPI" in validated.answer


def test_existing_inline_citations_unchanged() -> None:
    passage = "SQL JOIN combines rows."
    payload = _grounded_payload(
        answer="JOIN merges rows [S1].",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "SQL JOIN combines"}],
    )
    validated = apply_validated_answer_for_tests(payload, _evidence(passage))
    assert validated.answer == "JOIN merges rows [S1]."


def test_multiple_cited_sources_append_only_missing_markers() -> None:
    passages = (
        "First chunk about FastAPI.",
        "Second chunk about PostgreSQL.",
    )
    payload = _grounded_payload(
        answer="Stack uses FastAPI [S1] and a database.",
        cited=["S1", "S2"],
        quotes=[
            {"source_id": "S1", "quote": "First chunk about"},
            {"source_id": "S2", "quote": "Second chunk about"},
        ],
    )
    validated = apply_validated_answer_for_tests(
        payload,
        _evidence(*passages),
        question="What stack?",
    )
    assert "[S1]" in validated.answer
    assert "[S2]" in validated.answer
    assert validated.answer.endswith("[S2]")


def test_unknown_source_id_still_rejected() -> None:
    payload = _grounded_payload(
        answer="Answer text.",
        cited=["S9"],
        quotes=[{"source_id": "S9", "quote": "fabricated quote text"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(payload, _evidence("Evidence chunk."))
    assert exc_info.value.code == codes.UNKNOWN_CITED_SOURCE_ID


def test_fabricated_support_quote_still_rejected() -> None:
    payload = _grounded_payload(
        answer="Backend FastAPI.",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "not in the passage at all"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            payload,
            _evidence("Projede backend olarak FastAPI kullanılmaktadır."),
        )
    assert exc_info.value.code == codes.QUOTE_NOT_IN_SOURCE


def test_unsupported_formula_still_abstains_or_rejects() -> None:
    payload = _grounded_payload(
        answer="Formül: dL/dw = x · y",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "Neural networks use layers"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            payload,
            _evidence("Neural networks use layers and backpropagation."),
            question="Zincir kuralının matematiksel formülü nedir?",
        )
    assert exc_info.value.code == codes.UNSUPPORTED_FORMULA


def test_unsupported_year_not_normalized() -> None:
    payload = _grounded_payload(
        answer="Important year 1912.",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "Ocean liners carried"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            payload,
            _evidence("Ocean liners carried passengers."),
            question="When did Titanic sink?",
        )
    assert exc_info.value.code == codes.UNSUPPORTED_DATE


def test_insufficient_evidence_does_not_add_markers() -> None:
    payload = {
        "answer": "15 Nisan 1912 tarihinde battı.",
        "cited_source_ids": [],
        "evidence_sufficient": False,
        "support_quotes": [],
    }
    validated = apply_validated_answer_for_tests(
        payload,
        _evidence("Unrelated ships text."),
        question="Titanik ne zaman battı?",
    )
    assert validated.grounded is False
    assert "[S1]" not in validated.answer


def test_append_helper_only_uses_validated_ids() -> None:
    result = append_missing_inline_citations(
        "Answer body.",
        ["S1", "S2"],
        missing_source_ids={"S2"},
    )
    assert result == "Answer body. [S2]"
    assert "[S1]" not in result


def test_generation_succeeds_on_first_call_without_repair() -> None:
    passage = "Projede backend olarak FastAPI kullanılmaktadır."

    def generate(_request: OllamaChatRequest) -> str:
        return json.dumps(
            {
                "answer": "Backend teknolojisi FastAPI.",
                "cited_source_ids": ["S1"],
                "evidence_sufficient": True,
                "support_quotes": [
                    {"source_id": "S1", "quote": "FastAPI kullanılmaktadır"},
                ],
            },
        )

    validated = complete_and_validate_grounded_answer(
        generate,
        OllamaChatRequest(
            model="qwen3:1.7b",
            system_message="sys",
            user_message="user",
            max_output_tokens=128,
            timeout_seconds=5.0,
            base_url="http://127.0.0.1:11434",
        ),
        allowed_source_ids=frozenset({"S1"}),
        source_texts={"S1": passage},
        question="Projede hangi backend teknolojisi kullanılıyor?",
    )
    assert validated.grounded is True
    assert "[S1]" in validated.answer
