"""Validate structured model output and citation safety."""

import re
from dataclasses import dataclass

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import RagGroundingError
from ai_knowledge_hub_api.rag.evidence_support import (
    quote_found_in_source,
    validate_high_risk_answer_content,
)

_CITATION_IN_ANSWER = re.compile(r"\[S(\d+)\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    answer: str
    cited_source_ids: tuple[str, ...]
    grounded: bool


def _normalize_source_id(raw: str) -> str | None:
    normalized = raw.strip()
    if not normalized:
        return None
    upper = normalized.upper()
    if not upper.startswith("S") or not upper[1:].isdigit():
        return None
    return f"S{int(upper[1:])}"


def _parse_support_quotes(
    payload: dict[str, object],
    *,
    cited_ids: list[str],
    evidence_sufficient: bool,
    source_texts: dict[str, str],
) -> None:
    if "support_quotes" not in payload:
        raise RagGroundingError(
            "Model response missing support_quotes",
            code=codes.MISSING_SUPPORT_QUOTES,
        )

    raw_quotes = payload.get("support_quotes")
    if not isinstance(raw_quotes, list):
        raise RagGroundingError(
            "support_quotes must be an array",
            code=codes.INVALID_SUPPORT_QUOTES_TYPE,
        )

    if not evidence_sufficient:
        if raw_quotes:
            raise RagGroundingError(
                "evidence_sufficient is false but support_quotes were provided",
                code=codes.INSUFFICIENT_WITH_SUPPORT_QUOTES,
            )
        return

    quotes_by_source: dict[str, list[str]] = {source_id: [] for source_id in cited_ids}
    for entry in raw_quotes:
        if not isinstance(entry, dict):
            raise RagGroundingError(
                "support_quotes entries must be objects",
                code=codes.INVALID_SUPPORT_QUOTE_ENTRY,
            )
        source_raw = entry.get("source_id")
        quote_raw = entry.get("quote")
        if not isinstance(source_raw, str) or not isinstance(quote_raw, str):
            raise RagGroundingError(
                "support_quotes entries need source_id and quote strings",
                code=codes.INVALID_SUPPORT_QUOTE_ENTRY,
            )
        source_id = _normalize_source_id(source_raw)
        if source_id is None or source_id not in cited_ids:
            raise RagGroundingError(
                "support_quotes source_id must match a cited_source_ids entry",
                code=codes.INVALID_SUPPORT_QUOTE_ENTRY,
            )
        quotes_by_source.setdefault(source_id, []).append(quote_raw.strip())

    for source_id in cited_ids:
        quotes = quotes_by_source.get(source_id, [])
        if not quotes:
            raise RagGroundingError(
                "Each cited source needs at least one support quote",
                code=codes.MISSING_SUPPORT_QUOTE_FOR_SOURCE,
            )
        source_text = source_texts.get(source_id, "")
        if not any(quote_found_in_source(quote, source_text) for quote in quotes):
            raise RagGroundingError(
                "support_quotes must be verbatim substrings of the cited passage",
                code=codes.QUOTE_NOT_IN_SOURCE,
            )


def validate_grounded_answer(
    payload: dict[str, object],
    *,
    allowed_source_ids: frozenset[str],
    source_texts: dict[str, str] | None = None,
    question: str = "",
) -> ValidatedAnswer:
    answer = payload.get("answer")
    cited_raw = payload.get("cited_source_ids")
    resolved_source_texts = source_texts or {}

    if not isinstance(answer, str) or not answer.strip():
        raise RagGroundingError(
            "Model answer missing or empty", code=codes.MISSING_ANSWER
        )

    if "evidence_sufficient" not in payload:
        raise RagGroundingError(
            "Model response missing evidence_sufficient",
            code=codes.MISSING_EVIDENCE_SUFFICIENT,
        )

    evidence_sufficient_raw = payload.get("evidence_sufficient")
    if not isinstance(evidence_sufficient_raw, bool):
        raise RagGroundingError(
            "evidence_sufficient must be a boolean",
            code=codes.INVALID_EVIDENCE_SUFFICIENT_TYPE,
        )

    if cited_raw is None:
        cited_list: list[object] = []
    elif isinstance(cited_raw, list):
        cited_list = cited_raw
    else:
        raise RagGroundingError(
            "cited_source_ids must be an array",
            code=codes.INVALID_CITED_SOURCE_IDS_TYPE,
        )

    cited_ids: list[str] = []
    for item in cited_list:
        if not isinstance(item, str):
            raise RagGroundingError(
                "cited_source_ids must contain strings",
                code=codes.INVALID_CITED_SOURCE_ID,
            )
        source_id = _normalize_source_id(item)
        if source_id is None:
            raise RagGroundingError(
                "Invalid source id in cited_source_ids",
                code=codes.INVALID_CITED_SOURCE_ID,
            )
        cited_ids.append(source_id)

    if len(set(cited_ids)) != len(cited_ids):
        raise RagGroundingError(
            "Duplicate source ids in cited_source_ids",
            code=codes.DUPLICATE_CITED_SOURCE_ID,
        )

    unknown = [value for value in cited_ids if value not in allowed_source_ids]
    if unknown:
        raise RagGroundingError(
            "Cited source ids not present in retrieved evidence",
            code=codes.UNKNOWN_CITED_SOURCE_ID,
        )

    inline_ids = {
        _normalize_source_id(f"S{match.group(1)}")
        for match in _CITATION_IN_ANSWER.finditer(answer)
    }
    inline_ids.discard(None)
    inline_ids_typed = {value for value in inline_ids if value is not None}

    unknown_inline = [
        value for value in inline_ids_typed if value not in allowed_source_ids
    ]
    if unknown_inline:
        raise RagGroundingError(
            "Answer cites source ids not in retrieved evidence",
            code=codes.UNKNOWN_INLINE_CITATION,
        )

    _parse_support_quotes(
        payload,
        cited_ids=cited_ids,
        evidence_sufficient=evidence_sufficient_raw,
        source_texts={
            key: resolved_source_texts[key]
            for key in cited_ids
            if key in resolved_source_texts
        },
    )

    if not evidence_sufficient_raw:
        if cited_ids or inline_ids_typed:
            raise RagGroundingError(
                "evidence_sufficient is false but citations were provided",
                code=codes.INSUFFICIENT_WITH_CITATIONS,
            )
        return ValidatedAnswer(
            answer=answer.strip(),
            cited_source_ids=(),
            grounded=False,
        )

    if not cited_ids:
        raise RagGroundingError(
            "evidence_sufficient is true but no cited_source_ids were provided",
            code=codes.SUFFICIENT_WITHOUT_CITATIONS,
        )

    extra_inline = inline_ids_typed - set(cited_ids)
    if extra_inline:
        raise RagGroundingError(
            "Answer contains citations not listed in cited_source_ids",
            code=codes.EXTRA_INLINE_CITATION,
        )

    missing_inline = set(cited_ids) - inline_ids_typed
    if missing_inline:
        raise RagGroundingError(
            "cited_source_ids must appear in the answer as [Sx] markers",
            code=codes.MISSING_INLINE_CITATION,
        )

    cited_texts = {
        source_id: resolved_source_texts[source_id]
        for source_id in cited_ids
        if source_id in resolved_source_texts
    }
    validate_high_risk_answer_content(
        question=question,
        answer=answer,
        cited_texts=cited_texts,
    )

    return ValidatedAnswer(
        answer=answer.strip(),
        cited_source_ids=tuple(cited_ids),
        grounded=True,
    )
