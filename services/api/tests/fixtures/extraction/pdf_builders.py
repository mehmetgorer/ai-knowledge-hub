"""Minimal PDF bytes for extraction tests (no external fixture files)."""

from io import BytesIO

from pypdf import PdfWriter


def pdf_with_pages(page_labels: list[str]) -> bytes:
    """Build a minimal PDF with extractable text on each page."""
    if not page_labels:
        raise ValueError("page_labels must not be empty")

    page_objects: list[str] = []
    content_objects: list[str] = []
    font_obj_num = 3 + len(page_labels) * 2

    for index, label in enumerate(page_labels):
        page_num = 3 + index * 2
        content_num = page_num + 1
        escaped = label.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_stream = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET"
        content_objects.append(
            f"{content_num} 0 obj<< /Length {len(content_stream)} >>stream\n"
            f"{content_stream}\nendstream endobj"
        )
        page_objects.append(
            f"{page_num} 0 obj<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 612 792] /Contents {content_num} 0 R "
            f"/Resources<< /Font<< /F1 {font_obj_num} 0 R >> >> >> endobj"
        )

    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(page_labels)))
    font_obj = (
        f"{font_obj_num} 0 obj<< /Type /Font /Subtype /Type1 "
        f"/BaseFont /Helvetica >> endobj"
    )
    parts = [
        "%PDF-1.4",
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >> endobj",
        f"2 0 obj<< /Type /Pages /Kids [{kids}] /Count {len(page_labels)} >> endobj",
        *page_objects,
        *content_objects,
        font_obj,
        "xref",
        "0 1",
        "0000000000 65535 f ",
        "trailer<< /Size 1 >>",
        "startxref",
        "0",
        "%%EOF",
    ]
    return "\n".join(parts).encode("latin-1")


def blank_pdf_page() -> bytes:
    """PDF with a single blank page (no extractable text)."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
