"""Lightweight checks that cited quotes and high-risk facts appear in sources."""

import re

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import RagGroundingError

_CITATION_MARKER = re.compile(r"\[S\d+\]", re.IGNORECASE)
_MIN_QUOTE_LEN = 8
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_STANDALONE_NUMBER = re.compile(r"\b\d{3,}(?:[.,]\d+)?\b")
_FORMULA_QUESTION = (
    "formül",
    "formula",
    "equation",
    "matematiksel",
    "mathematical",
    "chain rule",
    "zincir kural",
)
_MATH_SYMBOLS = frozenset("=∂∑∫√^\\")


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def quote_found_in_source(quote: str, source_text: str) -> bool:
    normalized_quote = normalize_whitespace(quote.strip())
    if len(normalized_quote) < _MIN_QUOTE_LEN:
        return False
    normalized_source = normalize_whitespace(source_text)
    if normalized_quote in normalized_source:
        return True
    return normalized_quote.casefold() in normalized_source.casefold()


def question_requests_formula(question: str) -> bool:
    lower = question.casefold()
    return any(keyword in lower for keyword in _FORMULA_QUESTION)


def source_corpus_has_formula(cited_texts: dict[str, str]) -> bool:
    for text in cited_texts.values():
        if any(symbol in text for symbol in _MATH_SYMBOLS):
            return True
        if re.search(r"[a-zA-Z]\s*=\s*[^\s=]", text):
            return True
    return False


def answer_has_formula_like_claim(answer_without_citations: str) -> bool:
    text = answer_without_citations
    if "=" not in text and not any(symbol in text for symbol in _MATH_SYMBOLS):
        return False
    if any(symbol in text for symbol in _MATH_SYMBOLS):
        return True
    if re.search(r"\\frac|[dD][A-Za-z]/[dD][A-Za-z]", text):
        return True
    if re.search(r"[a-zA-Z]\s*=\s*[^\s=].*[\+\-\*/]", text):
        return True
    if re.search(r"[a-zA-Z]\s*=\s*[^\s=]{6,}", text):
        return True
    return False


def formula_claim_supported(
    answer_without_citations: str, cited_texts: dict[str, str]
) -> bool:
    if not answer_has_formula_like_claim(answer_without_citations):
        return True
    corpus = " ".join(cited_texts.values())
    normalized_answer = normalize_whitespace(answer_without_citations)
    normalized_corpus = normalize_whitespace(corpus)
    if normalized_answer in normalized_corpus:
        return True
    for segment in re.split(r"[.;]\s+", normalized_answer):
        if "=" in segment and segment in normalized_corpus:
            return True
        if "=" in segment and segment.casefold() in normalized_corpus.casefold():
            return True
    return False


def strip_citation_markers(answer: str) -> str:
    return normalize_whitespace(_CITATION_MARKER.sub(" ", answer))


def validate_high_risk_answer_content(
    *,
    question: str,
    answer: str,
    cited_texts: dict[str, str],
) -> None:
    if not cited_texts:
        return

    body = strip_citation_markers(answer)

    if question_requests_formula(question):
        if not source_corpus_has_formula(cited_texts) and answer_has_formula_like_claim(
            body,
        ):
            raise RagGroundingError(
                "Answer includes a formula not present in cited sources",
                code=codes.UNSUPPORTED_FORMULA,
            )
        if not formula_claim_supported(body, cited_texts):
            raise RagGroundingError(
                "Formula-like claim is not supported by cited passages",
                code=codes.UNSUPPORTED_FORMULA,
            )

    for year in _YEAR.findall(body):
        if not any(year in text for text in cited_texts.values()):
            raise RagGroundingError(
                "Answer includes a year not present in cited sources",
                code=codes.UNSUPPORTED_DATE,
            )

    for number in _STANDALONE_NUMBER.findall(body):
        if not any(number in text for text in cited_texts.values()):
            raise RagGroundingError(
                "Answer includes a numeric fact not present in cited sources",
                code=codes.UNSUPPORTED_NUMERIC,
            )
