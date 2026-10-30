"""Unit tests for generate → validate → repair grounded answers."""

import json
import logging
from dataclasses import replace

import pytest

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import RagFailClosedAbstention, RagGroundingError
from ai_knowledge_hub_api.rag.generation import complete_and_validate_grounded_answer
from ai_knowledge_hub_api.rag.ollama import OllamaChatRequest

_SOURCE_SNIPPET = "SQL JOIN combines rows from two tables."


def _chat_request() -> OllamaChatRequest:
    return OllamaChatRequest(
        model="qwen3:1.7b",
        system_message="sys",
        user_message="Question:\nJOIN?\n\nSource evidence:\n[S1] ...",
        max_output_tokens=128,
        timeout_seconds=5.0,
        base_url="http://127.0.0.1:11434",
    )


def _payload(
    *,
    answer: str,
    cited: list[str],
    evidence_sufficient: bool,
    support_quotes: list[dict[str, str]] | None = None,
) -> str:
    if support_quotes is None:
        if evidence_sufficient and cited:
            support_quotes = [
                {"source_id": source_id, "quote": _SOURCE_SNIPPET}
                for source_id in cited
            ]
        else:
            support_quotes = []
    return json.dumps(
        {
            "answer": answer,
            "cited_source_ids": cited,
            "evidence_sufficient": evidence_sufficient,
            "support_quotes": support_quotes,
        },
    )


def _texts() -> dict[str, str]:
    return {"S1": _SOURCE_SNIPPET}


def test_realistic_join_answer_with_inline_citation() -> None:
    allowed = frozenset({"S1"})

    def generate(_request: OllamaChatRequest) -> str:
        return _payload(
            answer=(
                "INNER JOIN yalnızca eşleşen satırları döndürür; "
                "LEFT JOIN eşleşmeyen sol satırları da tutar [S1]."
            ),
            cited=["S1"],
            evidence_sufficient=True,
        )

    validated = complete_and_validate_grounded_answer(
        generate,
        _chat_request(),
        allowed_source_ids=allowed,
        source_texts=_texts(),
        question="INNER JOIN ve LEFT JOIN farkı nedir?",
    )
    assert validated.grounded is True
    assert validated.cited_source_ids == ("S1",)


def test_missing_evidence_sufficient_rejected() -> None:
    allowed = frozenset({"S1"})
    calls = 0

    def generate(_request: OllamaChatRequest) -> str:
        nonlocal calls
        calls += 1
        return json.dumps({"answer": "x [S1]", "cited_source_ids": ["S1"]})

    with pytest.raises(RagGroundingError) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            _chat_request(),
            allowed_source_ids=allowed,
            source_texts=_texts(),
            question="Q?",
        )
    assert exc_info.value.code == codes.MISSING_EVIDENCE_SUFFICIENT
    assert calls == 2


def test_conflicting_insufficient_flag_with_citations_rejected() -> None:
    allowed = frozenset({"S1"})
    calls = 0

    def generate(_request: OllamaChatRequest) -> str:
        nonlocal calls
        calls += 1
        return _payload(
            answer="Still [S1].",
            cited=["S1"],
            evidence_sufficient=False,
        )

    with pytest.raises(RagFailClosedAbstention) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            _chat_request(),
            allowed_source_ids=allowed,
            source_texts=_texts(),
            question="Q?",
        )
    assert exc_info.value.code == codes.INSUFFICIENT_WITH_CITATIONS
    assert calls == 2


def test_missing_inline_citation_normalized_without_llm_repair() -> None:
    allowed = frozenset({"S1"})
    calls = 0

    def generate(_request: OllamaChatRequest) -> str:
        nonlocal calls
        calls += 1
        return _payload(
            answer="JOIN farkı açıklaması citations only in array.",
            cited=["S1"],
            evidence_sufficient=True,
        )

    validated = complete_and_validate_grounded_answer(
        generate,
        _chat_request(),
        allowed_source_ids=allowed,
        source_texts=_texts(),
        question="JOIN?",
    )
    assert validated.grounded is True
    assert "[S1]" in validated.answer
    assert calls == 1


def test_extra_inline_citation_still_rejected_after_repair() -> None:
    allowed = frozenset({"S1", "S2"})
    texts = {
        "S1": _SOURCE_SNIPPET,
        "S2": "Other passage text for second source.",
    }

    def generate(_request: OllamaChatRequest) -> str:
        return json.dumps(
            {
                "answer": "See [S1] and also [S2].",
                "cited_source_ids": ["S1"],
                "evidence_sufficient": True,
                "support_quotes": [
                    {"source_id": "S1", "quote": _SOURCE_SNIPPET},
                ],
            },
        )

    with pytest.raises(RagGroundingError) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            _chat_request(),
            allowed_source_ids=allowed,
            source_texts=texts,
            question="Q?",
        )
    assert exc_info.value.code == codes.EXTRA_INLINE_CITATION


def test_invented_source_id_rejected() -> None:
    allowed = frozenset({"S1"})

    def generate(_request: OllamaChatRequest) -> str:
        return _payload(
            answer="See [S9].",
            cited=["S9"],
            evidence_sufficient=True,
        )

    with pytest.raises(RagGroundingError) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            _chat_request(),
            allowed_source_ids=allowed,
            source_texts=_texts(),
            question="Q?",
        )
    assert exc_info.value.code == codes.UNKNOWN_CITED_SOURCE_ID


def test_malformed_json_maps_to_grounding_code() -> None:
    allowed = frozenset({"S1"})

    def generate(_request: OllamaChatRequest) -> str:
        return "not-json-at-all"

    with pytest.raises(RagGroundingError) as exc_info:
        complete_and_validate_grounded_answer(
            generate,
            _chat_request(),
            allowed_source_ids=allowed,
            source_texts=_texts(),
            question="Q?",
        )
    assert exc_info.value.code == codes.MALFORMED_JSON


def test_insufficient_evidence_abstains_without_citations() -> None:
    allowed = frozenset({"S1"})

    def generate(_request: OllamaChatRequest) -> str:
        return _payload(
            answer="Kaynaklar bu soruyu yanıtlamak için yeterli değil.",
            cited=[],
            evidence_sufficient=False,
        )

    validated = complete_and_validate_grounded_answer(
        generate,
        _chat_request(),
        allowed_source_ids=allowed,
        source_texts=_texts(),
        question="Soru?",
    )
    assert validated.grounded is False
    assert validated.cited_source_ids == ()


def test_validation_logs_only_code_not_sensitive_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    allowed = frozenset({"S1"})
    secret_question = "SECRET_USER_QUESTION_XYZ"
    secret_passage = "SECRET_PASSAGE_ABC"
    request = replace(
        _chat_request(),
        user_message=f"Question:\n{secret_question}\n\n{secret_passage}",
    )

    def generate(_req: OllamaChatRequest) -> str:
        return _payload(
            answer="Valid body without marker.",
            cited=["S1"],
            evidence_sufficient=True,
        )

    with caplog.at_level(logging.INFO):
        validated = complete_and_validate_grounded_answer(
            generate,
            request,
            allowed_source_ids=allowed,
            source_texts=_texts(),
            question=secret_question,
        )

    assert validated.grounded is True
    assert "[S1]" in validated.answer
    log_text = caplog.text
    assert "normalized sources=S1" in log_text
    assert secret_question not in log_text
    assert secret_passage not in log_text
    assert "Valid body" not in log_text
