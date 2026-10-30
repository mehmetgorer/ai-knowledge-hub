"""Deterministic inline [Sx] presentation for validated citations."""

import re

_CITATION_IN_ANSWER = re.compile(r"\[S(\d+)\]", re.IGNORECASE)


def append_missing_inline_citations(
    answer: str,
    cited_source_ids: list[str],
    *,
    missing_source_ids: set[str],
) -> str:
    """Append [Sx] markers for cited ids not already present in the answer."""
    if not missing_source_ids:
        return answer.strip()
    suffix_parts = [
        f"[{source_id}]"
        for source_id in cited_source_ids
        if source_id in missing_source_ids
    ]
    if not suffix_parts:
        return answer.strip()
    base = answer.rstrip()
    return f"{base} {' '.join(suffix_parts)}"


def inline_source_ids_in_answer(answer: str) -> set[str]:
    return {f"S{int(match.group(1))}" for match in _CITATION_IN_ANSWER.finditer(answer)}
