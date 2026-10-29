from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ai_knowledge_hub_api.documents.extraction.errors import (
    CorruptedDocumentError,
    EmptyExtractionError,
    EncryptedDocumentError,
    ExtractionLimitExceededError,
    InvalidTextEncodingError,
    UnsupportedExtractionFormatError,
)
from ai_knowledge_hub_api.documents.extraction.normalize import (
    normalize_extracted_text,
    normalize_markdown_text,
)
from ai_knowledge_hub_api.documents.extraction.types import (
    ExtractedPage,
    ExtractionLimits,
    ExtractionResult,
    SourceKind,
)

_ALLOWED_EXTENSIONS = frozenset({".pdf", ".txt", ".md"})
_PAGE_JOIN = "\n\n"


def _extension_from_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        return ""
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in _ALLOWED_EXTENSIONS else ""


def _decode_utf8_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidTextEncodingError("Text document must be valid UTF-8") from exc


def _open_pdf_reader(content: bytes) -> PdfReader:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
    except PdfReadError as exc:
        raise CorruptedDocumentError("PDF file is corrupted or unreadable") from exc
    except Exception as exc:
        raise CorruptedDocumentError("PDF file is corrupted or unreadable") from exc

    try:
        is_encrypted = reader.is_encrypted
    except Exception as exc:
        raise CorruptedDocumentError(
            "PDF encryption metadata could not be read"
        ) from exc

    if is_encrypted:
        raise EncryptedDocumentError("PDF is encrypted or password-protected")

    return reader


def _pdf_total_page_count(reader: PdfReader) -> int:
    try:
        page_count = len(reader.pages)
    except Exception as exc:
        raise CorruptedDocumentError("PDF page count could not be determined") from exc
    return page_count


def _extract_pdf_page_text(reader: PdfReader, page_index: int) -> str:
    try:
        page = reader.pages[page_index]
        return page.extract_text() or ""
    except Exception as exc:
        raise CorruptedDocumentError(
            f"Failed to read PDF page {page_index + 1}"
        ) from exc


def _apply_character_limit(
    pages: list[ExtractedPage],
    *,
    max_characters: int,
    normalize_joined: bool = True,
) -> tuple[tuple[ExtractedPage, ...], str, bool]:
    truncated = False
    limited_pages: list[ExtractedPage] = []
    remaining = max_characters
    full_parts: list[str] = []

    for page in pages:
        if remaining <= 0:
            truncated = True
            break
        if full_parts:
            if len(_PAGE_JOIN) > remaining:
                truncated = True
                break
            remaining -= len(_PAGE_JOIN)
        page_text = page.text
        if len(page_text) > remaining:
            page_text = page_text[:remaining]
            truncated = True
        if page_text:
            limited_pages.append(
                ExtractedPage(page_number=page.page_number, text=page_text)
            )
            full_parts.append(page_text)
        remaining -= len(page_text)
        if truncated:
            break

    full_text = _PAGE_JOIN.join(full_parts)
    if normalize_joined:
        full_text = normalize_extracted_text(full_text)
    if len(full_text) > max_characters:
        full_text = full_text[:max_characters]
        truncated = True

    return tuple(limited_pages), full_text, truncated


def _extract_pdf(content: bytes, limits: ExtractionLimits) -> ExtractionResult:
    reader = _open_pdf_reader(content)
    total_pages = _pdf_total_page_count(reader)
    if total_pages == 0:
        raise EmptyExtractionError("PDF contains no pages")

    pages_to_process = min(total_pages, limits.max_pdf_pages)
    truncated_pages = total_pages > limits.max_pdf_pages
    char_budget = limits.max_extracted_characters
    truncated_chars = False

    kept_pages: list[ExtractedPage] = []
    text_parts: list[str] = []
    saw_extractable_text = False

    for index in range(pages_to_process):
        if char_budget <= 0:
            truncated_chars = True
            break

        if text_parts:
            if len(_PAGE_JOIN) > char_budget:
                truncated_chars = True
                break
            char_budget -= len(_PAGE_JOIN)

        extracted = _extract_pdf_page_text(reader, index)
        page_text = normalize_extracted_text(extracted)
        if page_text.strip():
            saw_extractable_text = True

        if len(page_text) > char_budget:
            page_text = page_text[:char_budget]
            truncated_chars = True

        kept_pages.append(
            ExtractedPage(page_number=index + 1, text=page_text),
        )
        text_parts.append(page_text)
        char_budget -= len(page_text)

        if truncated_chars:
            break

    if not saw_extractable_text:
        raise EmptyExtractionError(
            "No extractable text found in PDF (it may be image-only or scanned)"
        )

    full_text = _PAGE_JOIN.join(text_parts)
    if len(full_text) > limits.max_extracted_characters:
        full_text = full_text[: limits.max_extracted_characters]
        truncated_chars = True

    if not full_text.strip():
        raise EmptyExtractionError(
            "No extractable text found in PDF (it may be image-only or scanned)"
        )

    return ExtractionResult(
        source_kind="pdf",
        pages=tuple(kept_pages),
        text=full_text,
        page_count=total_pages,
        truncated=truncated_pages or truncated_chars,
    )


def _extract_plain_text(
    content: bytes,
    *,
    source_kind: SourceKind,
    limits: ExtractionLimits,
) -> ExtractionResult:
    decoded = _decode_utf8_text(content)
    if source_kind == "markdown":
        normalized = normalize_markdown_text(decoded)
    else:
        normalized = normalize_extracted_text(decoded)
    if not normalized:
        raise EmptyExtractionError("Document contains no extractable text")

    page = ExtractedPage(page_number=1, text=normalized)
    limited_pages, full_text, truncated = _apply_character_limit(
        [page],
        max_characters=limits.max_extracted_characters,
        normalize_joined=source_kind != "markdown",
    )
    if not full_text.strip():
        raise EmptyExtractionError("Document contains no extractable text")

    return ExtractionResult(
        source_kind=source_kind,
        pages=limited_pages,
        text=full_text,
        page_count=1,
        truncated=truncated,
    )


def extract_document_text(
    content: bytes,
    *,
    filename: str | None = None,
    limits: ExtractionLimits | None = None,
) -> ExtractionResult:
    """
    Extract normalized text from PDF, TXT, or Markdown bytes.

    Does not read from storage or mutate database state.
    """
    resolved_limits = limits or ExtractionLimits()
    if resolved_limits.max_pdf_pages < 1:
        raise ExtractionLimitExceededError("max_pdf_pages must be at least 1")
    if resolved_limits.max_extracted_characters < 1:
        raise ExtractionLimitExceededError(
            "max_extracted_characters must be at least 1"
        )

    extension = _extension_from_filename(filename)
    if not extension:
        raise UnsupportedExtractionFormatError(
            "Unsupported document type for extraction; allowed: PDF, TXT, MD"
        )

    if extension == ".pdf":
        return _extract_pdf(content, resolved_limits)
    if extension == ".md":
        return _extract_plain_text(
            content, source_kind="markdown", limits=resolved_limits
        )
    return _extract_plain_text(content, source_kind="text", limits=resolved_limits)
