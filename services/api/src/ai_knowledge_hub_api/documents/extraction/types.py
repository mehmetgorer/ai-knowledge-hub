from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["pdf", "text", "markdown"]


@dataclass(frozen=True)
class ExtractionLimits:
    max_pdf_pages: int = 500
    max_extracted_characters: int = 512_000


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    source_kind: SourceKind
    pages: tuple[ExtractedPage, ...]
    text: str
    page_count: int
    truncated: bool
