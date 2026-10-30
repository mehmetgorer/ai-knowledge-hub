"""Unit tests for fail-closed abstention and evidence support heuristics."""

import json
import uuid

import pytest

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.abstention import build_insufficient_sources_answer
from ai_knowledge_hub_api.rag.errors import RagFailClosedAbstention, RagGroundingError
from ai_knowledge_hub_api.rag.evidence import EvidenceSource
from ai_knowledge_hub_api.rag.evidence_support import quote_found_in_source
from ai_knowledge_hub_api.rag.generation import complete_and_validate_grounded_answer
from ai_knowledge_hub_api.rag.ollama import OllamaChatRequest
from ai_knowledge_hub_api.rag.service import apply_validated_answer_for_tests
from ai_knowledge_hub_api.search.service import SemanticSearchMatch


def _evidence(text: str, source_id: str = "S1") -> list[EvidenceSource]:
    match = SemanticSearchMatch(
        document_id=uuid.uuid4(),
        original_filename="doc.txt",
        chunk_index=0,
        text=text,
        source_kind="text",
        page_numbers=(1,),
        cosine_distance=0.12,
    )
    return [EvidenceSource(source_id=source_id, match=match)]


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


def test_fail_closed_message_turkish() -> None:
    message = build_insufficient_sources_answer("SQL JOIN nedir?")
    assert "yeterli kaynak" in message


def test_supported_join_paraphrase_with_verbatim_quote() -> None:
    passage = (
        "INNER JOIN yalnızca eşleşen satırları döndürür; LEFT JOIN ise "
        "sol tablodaki tüm satırları korur."
    )
    payload = _grounded_payload(
        answer="INNER JOIN eşleşen satırları döndürür [S1].",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "INNER JOIN yalnızca eşleşen"}],
    )
    validated = apply_validated_answer_for_tests(
        payload,
        _evidence(passage),
        question="INNER JOIN ve LEFT JOIN farkı nedir?",
    )
    assert validated.grounded is True


def test_invented_chain_rule_formula_rejected() -> None:
    passage = "Neural networks use layers and backpropagation."
    payload = _grounded_payload(
        answer="Zincir kuralı ∂L/∂w = δ · x şeklindedir [S1].",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "Neural networks use layers"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            payload,
            _evidence(passage),
            question="Backpropagation işleminde zincir kuralının formülü nedir?",
        )
    assert exc_info.value.code == codes.UNSUPPORTED_FORMULA


def test_invented_historical_date_rejected_when_grounded() -> None:
    passage = "Ocean liners carried passengers across the Atlantic."
    payload = _grounded_payload(
        answer="Titanic 15 Nisan 1912 tarihinde battı [S1].",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "Ocean liners carried"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(
            payload,
            _evidence(passage),
            question="Titanik gemisi hangi tarihte battı?",
        )
    assert exc_info.value.code == codes.UNSUPPORTED_DATE


def test_fake_support_quote_not_in_passage() -> None:
    passage = "SQL JOIN combines rows."
    payload = _grounded_payload(
        answer="JOIN merges rows [S1].",
        cited=["S1"],
        quotes=[{"source_id": "S1", "quote": "totally fabricated snippet"}],
    )
    with pytest.raises(RagGroundingError) as exc_info:
        apply_validated_answer_for_tests(payload, _evidence(passage))
    assert exc_info.value.code == codes.QUOTE_NOT_IN_SOURCE


def test_generation_maps_support_failure_to_fail_closed() -> None:
    allowed = frozenset({"S1"})
    texts = {"S1": "Only plain text about joins."}

    def generate(_request: OllamaChatRequest) -> str:
        return json.dumps(
            {
                "answer": "Year 1912 is important [S1].",
                "cited_source_ids": ["S1"],
                "evidence_sufficient": True,
                "support_quotes": [
                    {"source_id": "S1", "quote": "Only plain text"},
                ],
            },
        )

    with pytest.raises(RagFailClosedAbstention) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            OllamaChatRequest(
                model="qwen3:1.7b",
                system_message="sys",
                user_message="user",
                max_output_tokens=64,
                timeout_seconds=1.0,
                base_url="http://127.0.0.1:11434",
            ),
            allowed_source_ids=allowed,
            source_texts=texts,
            question="When did it happen?",
        )
    assert exc_info.value.code == codes.UNSUPPORTED_DATE


def test_quote_matching_allows_case_insensitive_substring() -> None:
    source = "SQL JOIN combines rows from TWO tables."
    assert quote_found_in_source("combines rows from two", source)
