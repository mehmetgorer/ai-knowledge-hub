"""Safe validation failure categories (logged server-side only)."""

MISSING_ANSWER = "missing_answer"
MISSING_EVIDENCE_SUFFICIENT = "missing_evidence_sufficient"
INVALID_EVIDENCE_SUFFICIENT_TYPE = "invalid_evidence_sufficient_type"
INVALID_CITED_SOURCE_IDS_TYPE = "invalid_cited_source_ids_type"
INVALID_CITED_SOURCE_ID = "invalid_cited_source_id"
DUPLICATE_CITED_SOURCE_ID = "duplicate_cited_source_id"
UNKNOWN_CITED_SOURCE_ID = "unknown_cited_source_id"
UNKNOWN_INLINE_CITATION = "unknown_inline_citation"
INSUFFICIENT_WITH_CITATIONS = "insufficient_with_citations"
SUFFICIENT_WITHOUT_CITATIONS = "sufficient_without_citations"
EXTRA_INLINE_CITATION = "extra_inline_citation"
MISSING_INLINE_CITATION = "missing_inline_citation"
MALFORMED_JSON = "malformed_json"
MISSING_SUPPORT_QUOTES = "missing_support_quotes"
INVALID_SUPPORT_QUOTES_TYPE = "invalid_support_quotes_type"
INVALID_SUPPORT_QUOTE_ENTRY = "invalid_support_quote_entry"
MISSING_SUPPORT_QUOTE_FOR_SOURCE = "missing_support_quote_for_source"
QUOTE_NOT_IN_SOURCE = "quote_not_in_source"
INSUFFICIENT_WITH_SUPPORT_QUOTES = "insufficient_with_support_quotes"
UNSUPPORTED_FORMULA = "unsupported_formula"
UNSUPPORTED_DATE = "unsupported_date"
UNSUPPORTED_NUMERIC = "unsupported_numeric"

FAIL_CLOSED_ABSTENTION_CODES = frozenset(
    {
        MISSING_SUPPORT_QUOTE_FOR_SOURCE,
        QUOTE_NOT_IN_SOURCE,
        UNSUPPORTED_FORMULA,
        UNSUPPORTED_DATE,
        UNSUPPORTED_NUMERIC,
    }
)
