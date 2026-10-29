import pytest

from ai_knowledge_hub_api.documents.extraction import (
    CorruptedDocumentError,
    EmptyExtractionError,
    EncryptedDocumentError,
    ExtractionLimits,
    InvalidTextEncodingError,
    UnsupportedExtractionFormatError,
    extract_document_text,
)
from ai_knowledge_hub_api.documents.extraction.normalize import (
    normalize_extracted_text,
    normalize_markdown_text,
)
from tests.fixtures.extraction.pdf_builders import (
    blank_pdf_page,
    encrypted_pdf_bytes,
    pdf_with_pages,
)


def test_extract_utf8_txt() -> None:
    content = b"Line one\n\nLine two  with spaces\n"
    result = extract_document_text(content, filename="notes.txt")
    assert result.source_kind == "text"
    assert result.page_count == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert "Line one" in result.text
    assert "Line two with spaces" in result.text
    assert result.truncated is False


def test_extract_utf8_markdown_preserves_structure() -> None:
    content = b"# Heading\n\nParagraph **bold**.\n\n- item"
    result = extract_document_text(content, filename="readme.md")
    assert result.source_kind == "markdown"
    assert "# Heading" in result.text
    assert "**bold**" in result.text
    assert "- item" in result.text


def test_extract_invalid_utf8_txt_raises() -> None:
    with pytest.raises(InvalidTextEncodingError):
        extract_document_text(b"\xff\xfe", filename="bad.txt")


def test_extract_pdf_single_page() -> None:
    pdf_bytes = pdf_with_pages(["Hello PDF"])
    result = extract_document_text(pdf_bytes, filename="doc.pdf")
    assert result.source_kind == "pdf"
    assert result.page_count == 1
    assert len(result.pages) == 1
    assert "Hello PDF" in result.text


def test_extract_pdf_multi_page() -> None:
    pdf_bytes = pdf_with_pages(["Alpha page", "Beta page"])
    result = extract_document_text(pdf_bytes, filename="multi.pdf")
    assert result.page_count == 2
    assert len(result.pages) == 2
    assert result.pages[0].text == "Alpha page"
    assert result.pages[1].text == "Beta page"
    assert "Alpha page" in result.text
    assert "Beta page" in result.text


def test_extract_corrupted_pdf_raises() -> None:
    with pytest.raises(CorruptedDocumentError):
        extract_document_text(b"%PDF-1.4\nnot-a-real-pdf", filename="broken.pdf")


def test_extract_image_only_pdf_raises_empty() -> None:
    with pytest.raises(EmptyExtractionError):
        extract_document_text(blank_pdf_page(), filename="scan.pdf")


def test_normalize_whitespace_collapses_runs_not_paragraphs() -> None:
    raw = "Title\n\nPara   one\n\n\n\nPara two  end  "
    normalized = normalize_extracted_text(raw)
    assert normalized == "Title\n\nPara one\n\nPara two end"


def test_extract_character_limit_truncates() -> None:
    content = b"a" * 100
    limits = ExtractionLimits(max_extracted_characters=20)
    result = extract_document_text(content, filename="long.txt", limits=limits)
    assert result.truncated is True
    assert len(result.text) <= 20


def test_extract_pdf_page_limit() -> None:
    pdf_bytes = pdf_with_pages([f"Page {index}" for index in range(1, 6)])
    limits = ExtractionLimits(max_pdf_pages=2, max_extracted_characters=10_000)
    result = extract_document_text(pdf_bytes, filename="many.pdf", limits=limits)
    assert result.page_count == 5
    assert len(result.pages) == 2
    assert result.truncated is True
    assert "Page 1" in result.text
    assert "Page 2" in result.text
    assert "Page 5" not in result.text


def test_unsupported_extension_raises() -> None:
    with pytest.raises(UnsupportedExtractionFormatError):
        extract_document_text(b"data", filename="file.bin")


def test_normalize_markdown_preserves_fenced_python_and_nested_lists() -> None:
    raw = """# Title

Intro with  extra   spaces.

- outer
  - nested item

```python
def greet(name: str) -> str:
    return f"hello {name}"
```
"""
    normalized = normalize_markdown_text(raw)
    assert "Intro with extra spaces." in normalized
    assert "  - nested item" in normalized
    assert "def greet(name: str) -> str:" in normalized
    assert '    return f"hello {name}"' in normalized


def test_extract_markdown_python_fence_remains_valid() -> None:
    content = b"""# API

```python
def add(a: int, b: int) -> int:
    return a + b
```
"""
    result = extract_document_text(content, filename="guide.md")
    assert "def add(a: int, b: int) -> int:" in result.text
    assert "    return a + b" in result.text


def test_pdf_character_limit_stops_processing_later_pages() -> None:
    labels = [f"{'word ' * 25}page {index}" for index in range(1, 8)]
    pdf_bytes = pdf_with_pages(labels)
    limits = ExtractionLimits(max_pdf_pages=7, max_extracted_characters=90)
    result = extract_document_text(pdf_bytes, filename="big.pdf", limits=limits)
    assert result.truncated is True
    assert len(result.pages) < 7
    assert len(result.text) <= 90
    assert "page 7" not in result.text


def test_encrypted_pdf_raises_typed_error() -> None:
    with pytest.raises(EncryptedDocumentError):
        extract_document_text(encrypted_pdf_bytes(), filename="locked.pdf")


def test_pdf_page_count_failure_is_corrupted_document() -> None:
    from unittest.mock import MagicMock, patch

    mock_reader = MagicMock()
    mock_reader.is_encrypted = False
    mock_reader.pages.__len__.side_effect = RuntimeError("broken page tree")

    with patch(
        "ai_knowledge_hub_api.documents.extraction.service._open_pdf_reader",
        return_value=mock_reader,
    ):
        with pytest.raises(CorruptedDocumentError, match="page count"):
            extract_document_text(b"%PDF-1.4\n", filename="bad-pages.pdf")
