"""One-shot structural repair prompts for invalid model JSON."""

from ai_knowledge_hub_api.rag import validation_codes as codes

_REPAIR_HINTS: dict[str, str] = {
    codes.MISSING_ANSWER: (
        "Provide a non-empty answer string grounded only in the sources."
    ),
    codes.MISSING_EVIDENCE_SUFFICIENT: (
        "Include evidence_sufficient as a JSON boolean (true or false)."
    ),
    codes.INVALID_EVIDENCE_SUFFICIENT_TYPE: (
        "evidence_sufficient must be a JSON boolean, not a string or number."
    ),
    codes.INVALID_CITED_SOURCE_IDS_TYPE: (
        "cited_source_ids must be a JSON array of strings."
    ),
    codes.INVALID_CITED_SOURCE_ID: (
        'Each cited_source_ids entry must look like "S1", "S2", etc.'
    ),
    codes.DUPLICATE_CITED_SOURCE_ID: (
        "Do not repeat the same source id in cited_source_ids."
    ),
    codes.UNKNOWN_CITED_SOURCE_ID: (
        "Only cite source ids that appear in the supplied evidence list."
    ),
    codes.UNKNOWN_INLINE_CITATION: (
        "Inline [Sx] markers must only reference supplied source ids."
    ),
    codes.INSUFFICIENT_WITH_CITATIONS: (
        "When evidence_sufficient is false, cited_source_ids must be [] and "
        "the answer must not contain [Sx] markers."
    ),
    codes.SUFFICIENT_WITHOUT_CITATIONS: (
        "When evidence_sufficient is true, cited_source_ids must list every "
        "source you rely on."
    ),
    codes.EXTRA_INLINE_CITATION: (
        "Every [Sx] marker in answer must also appear in cited_source_ids."
    ),
    codes.MISSING_INLINE_CITATION: (
        "When evidence_sufficient is true, every id in cited_source_ids must "
        "appear in answer as an inline [Sx] marker (example: ... [S1] ...)."
    ),
    codes.MALFORMED_JSON: (
        "Return only one JSON object with answer, evidence_sufficient, and "
        "cited_source_ids — no prose outside the object."
    ),
}


def build_repair_user_message(
    original_user_message: str,
    *,
    validation_code: str,
    allowed_source_ids: tuple[str, ...],
) -> str:
    hint = _REPAIR_HINTS.get(
        validation_code,
        "Fix the JSON structure to satisfy the grounded answer schema.",
    )
    allowed = ", ".join(allowed_source_ids) if allowed_source_ids else "(none)"
    return (
        f"{original_user_message}\n\n"
        "CORRECTION REQUIRED (formatting only — do not invent facts or "
        "change evidence_sufficient unless the sources truly cannot answer):\n"
        f"- validation_code: {validation_code}\n"
        f"- allowed_source_ids: {allowed}\n"
        f"- {hint}\n"
        "Return only one JSON object matching the schema."
    )
