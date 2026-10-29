import pytest

from ai_knowledge_hub_api.documents.chunking import (
    ChunkingConfig,
    ChunkingConfigurationError,
    ChunkingLimitExceededError,
    chunk_extraction_result,
    collect_chunk_units_for_coverage,
    validate_chunking_config,
)
from ai_knowledge_hub_api.documents.extraction import extract_document_text
from ai_knowledge_hub_api.documents.extraction.types import (
    ExtractedPage,
    ExtractionResult,
)
from tests.fixtures.extraction.pdf_builders import pdf_with_pages


def _extraction_from_text(
    text: str,
    *,
    source_kind: str = "text",
) -> ExtractionResult:
    return ExtractionResult(
        source_kind=source_kind,  # type: ignore[arg-type]
        pages=(ExtractedPage(page_number=1, text=text),),
        text=text,
        page_count=1,
        truncated=False,
    )


def test_short_document_single_chunk() -> None:
    extraction = _extraction_from_text("Hello world.")
    result = chunk_extraction_result(
        extraction,
        config=ChunkingConfig(target_characters=200, max_characters=300),
    )
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_index == 0
    assert result.chunks[0].text == "Hello world."
    assert result.chunks[0].character_count == len(result.chunks[0].text)


def test_long_paragraph_splits_on_sentence_boundaries() -> None:
    sentence = "Word " * 40
    text = (sentence.strip() + ". ") * 8
    extraction = _extraction_from_text(text.strip())
    config = ChunkingConfig(
        target_characters=120,
        max_characters=180,
        overlap_characters=0,
    )
    result = chunk_extraction_result(extraction, config=config)
    assert len(result.chunks) > 1
    for chunk in result.chunks:
        assert chunk.character_count <= config.max_characters
        assert chunk.text.strip()


def test_overlap_repeated_between_consecutive_chunks() -> None:
    text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph."
    extraction = _extraction_from_text(text)
    config = ChunkingConfig(
        target_characters=35,
        max_characters=60,
        overlap_characters=12,
    )
    result = chunk_extraction_result(extraction, config=config)
    assert len(result.chunks) >= 2
    first_tail = result.chunks[0].text[-12:]
    assert first_tail in result.chunks[1].text


def test_pdf_chunks_are_page_local() -> None:
    pdf_bytes = pdf_with_pages(["Page one text", "Page two text"])
    extraction = extract_document_text(pdf_bytes, filename="doc.pdf")
    config = ChunkingConfig(
        target_characters=50,
        max_characters=80,
        overlap_characters=0,
    )
    result = chunk_extraction_result(extraction, config=config)
    assert len(result.chunks) >= 2
    page_one_chunks = [c for c in result.chunks if c.page_numbers == (1,)]
    page_two_chunks = [c for c in result.chunks if c.page_numbers == (2,)]
    assert page_one_chunks
    assert page_two_chunks
    assert all("Page one" in c.text or "one" in c.text for c in page_one_chunks)
    assert all("Page two" in c.text for c in page_two_chunks)


def test_markdown_heading_and_python_code_block() -> None:
    text = """# Title

Intro paragraph.

```python
def add(a: int, b: int) -> int:
    return a + b
```
"""
    extraction = _extraction_from_text(text, source_kind="markdown")
    result = chunk_extraction_result(
        extraction,
        config=ChunkingConfig(target_characters=500, max_characters=800),
    )
    combined = "\n".join(chunk.text for chunk in result.chunks)
    assert "# Title" in combined
    assert "def add(a: int, b: int) -> int:" in combined
    assert "return a + b" in combined


def test_turkish_unicode_text() -> None:
    text = "İstanbul'da güzel bir gün. Öğrenciler çalışıyor."
    extraction = _extraction_from_text(text)
    result = chunk_extraction_result(extraction)
    assert len(result.chunks) == 1
    assert "İstanbul" in result.chunks[0].text


def test_chunking_is_deterministic() -> None:
    text = "Paragraph A.\n\nParagraph B.\n\nParagraph C."
    extraction = _extraction_from_text(text)
    config = ChunkingConfig(
        target_characters=30, max_characters=50, overlap_characters=5
    )
    first = chunk_extraction_result(extraction, config=config)
    second = chunk_extraction_result(extraction, config=config)
    assert first == second


def test_invalid_overlap_configuration() -> None:
    with pytest.raises(ChunkingConfigurationError):
        validate_chunking_config(
            ChunkingConfig(max_characters=100, overlap_characters=100),
        )


def test_max_chunks_limit_raises() -> None:
    text = "Section.\n\n" * 30
    extraction = _extraction_from_text(text)
    config = ChunkingConfig(
        target_characters=20,
        max_characters=30,
        overlap_characters=0,
        max_chunks=2,
    )
    with pytest.raises(ChunkingLimitExceededError):
        chunk_extraction_result(extraction, config=config)


def test_source_units_appear_in_chunk_output() -> None:
    text = "# Heading\n\nBody text.\n\n```python\nx = 1\n```\n\nTail section."
    extraction = _extraction_from_text(text, source_kind="markdown")
    config = ChunkingConfig(
        target_characters=40,
        max_characters=70,
        overlap_characters=8,
    )
    result = chunk_extraction_result(extraction, config=config)
    units = collect_chunk_units_for_coverage(extraction)
    for unit in units:
        assert any(unit in chunk.text for chunk in result.chunks)


def test_no_empty_chunks_emitted() -> None:
    extraction = _extraction_from_text("Only content.")
    result = chunk_extraction_result(extraction)
    assert all(chunk.text.strip() for chunk in result.chunks)
    assert [chunk.chunk_index for chunk in result.chunks] == list(
        range(len(result.chunks)),
    )
