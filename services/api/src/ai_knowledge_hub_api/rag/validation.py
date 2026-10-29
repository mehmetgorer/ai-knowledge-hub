"""Validate structured model output and citation safety."""

import json
import re
from dataclasses import dataclass

from ai_knowledge_hub_api.rag.errors import RagGroundingError, RagOllamaResponseError

_CITATION_IN_ANSWER = re.compile(r"\[S(\d+)\]")


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    answer: str
    cited_source_ids: tuple[str, ...]
    grounded: bool


def parse_structured_completion(raw_content: str) -> dict[str, object]:
    stripped = raw_content.strip()
    if not stripped:
        raise RagOllamaResponseError("Empty model response")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise RagOllamaResponseError("Model response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RagOllamaResponseError("Model response JSON must be an object")
    return payload


def validate_grounded_answer(
    payload: dict[str, object],
    *,
    allowed_source_ids: frozenset[str],
) -> ValidatedAnswer:
    answer = payload.get("answer")
    cited_raw = payload.get("cited_source_ids")

    if not isinstance(answer, str) or not answer.strip():
        raise RagGroundingError("Model answer missing or empty")

    if cited_raw is None:
        cited_list: list[object] = []
    elif isinstance(cited_raw, list):
        cited_list = cited_raw
    else:
        raise RagGroundingError("cited_source_ids must be an array")

    cited_ids: list[str] = []
    for item in cited_list:
        if not isinstance(item, str) or not item.strip():
            raise RagGroundingError("cited_source_ids must contain non-empty strings")
        normalized = item.strip()
        if not normalized.startswith("S") or not normalized[1:].isdigit():
            raise RagGroundingError("Invalid source id in cited_source_ids")
        source_id = f"S{int(normalized[1:])}"
        cited_ids.append(source_id)

    if len(set(cited_ids)) != len(cited_ids):
        raise RagGroundingError("Duplicate source ids in cited_source_ids")

    unknown = [value for value in cited_ids if value not in allowed_source_ids]
    if unknown:
        raise RagGroundingError("Cited source ids not present in retrieved evidence")

    inline_ids = {
        f"S{match.group(1)}" for match in _CITATION_IN_ANSWER.finditer(answer)
    }
    unknown_inline = [value for value in inline_ids if value not in allowed_source_ids]
    if unknown_inline:
        raise RagGroundingError("Answer cites source ids not in retrieved evidence")

    if not cited_ids:
        if inline_ids:
            raise RagGroundingError(
                "Answer cites sources but cited_source_ids is empty",
            )
        return ValidatedAnswer(
            answer=answer.strip(),
            cited_source_ids=(),
            grounded=False,
        )

    extra_inline = inline_ids - set(cited_ids)
    if extra_inline:
        raise RagGroundingError(
            "Answer contains citations not listed in cited_source_ids"
        )

    missing_inline = set(cited_ids) - inline_ids
    if missing_inline:
        raise RagGroundingError(
            "cited_source_ids must appear in the answer as [Sx] markers"
        )

    return ValidatedAnswer(
        answer=answer.strip(),
        cited_source_ids=tuple(cited_ids),
        grounded=True,
    )
