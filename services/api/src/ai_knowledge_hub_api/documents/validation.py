import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = frozenset({".pdf", ".txt", ".md"})


class DocumentUploadValidationError(Exception):
    """Raised when an uploaded file fails server-side validation."""


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    mime_type: str
    content: bytes
    content_hash_sha256: str


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _safe_basename(filename: str | None) -> str:
    if not filename or not filename.strip():
        return "upload"
    name = Path(filename).name
    if not name or name in {".", ".."}:
        return "upload"
    return name


def _extension_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in ALLOWED_EXTENSIONS else ""


def _detect_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _detect_text_file(data: bytes, extension: str) -> bool:
    if extension not in {".txt", ".md"}:
        return False
    if not data:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentUploadValidationError("Text uploads must be valid UTF-8") from exc
    return True


def validate_upload_content(
    *,
    filename: str | None,
    data: bytes,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> ValidatedUpload:
    if len(data) == 0:
        raise DocumentUploadValidationError("Uploaded file is empty")
    if len(data) > max_bytes:
        raise DocumentUploadValidationError(
            f"File exceeds maximum size of {max_bytes} bytes"
        )

    basename = _safe_basename(filename)
    extension = _extension_for_filename(basename)
    if not extension:
        raise DocumentUploadValidationError(
            "Unsupported file type; allowed: PDF, TXT, MD"
        )

    if extension == ".pdf":
        if not _detect_pdf(data):
            raise DocumentUploadValidationError(
                "File content does not match a valid PDF"
            )
        mime_type = "application/pdf"
    elif _detect_text_file(data, extension):
        mime_type = "text/markdown" if extension == ".md" else "text/plain"
    else:
        raise DocumentUploadValidationError(
            "File content does not match the declared type"
        )

    return ValidatedUpload(
        original_filename=basename,
        mime_type=mime_type,
        content=data,
        content_hash_sha256=_sha256_hex(data),
    )


def generate_storage_key(collection_id: uuid.UUID) -> str:
    return f"documents/{collection_id}/{uuid.uuid4()}"
