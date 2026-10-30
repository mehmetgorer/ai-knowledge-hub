"""Validate structured model output and citation safety."""

import re
from dataclasses import dataclass

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import RagGroundingError

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


def validate_grounded_answer(
    payload: dict[str, object],
    *,
    allowed_source_ids: frozenset[str],
) -> ValidatedAnswer:
    answer = payload.get("answer")
    cited_raw = payload.get("cited_source_ids")

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

    return ValidatedAnswer(
        answer=answer.strip(),
        cited_source_ids=tuple(cited_ids),
        grounded=True,
    )
