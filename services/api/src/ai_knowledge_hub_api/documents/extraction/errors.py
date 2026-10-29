"""Typed errors for document text extraction (no document content in messages)."""


class DocumentExtractionError(Exception):
    """Base class for extraction failures."""

    code: str = "extraction_failed"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedExtractionFormatError(DocumentExtractionError):
    code = "unsupported_format"


class InvalidTextEncodingError(DocumentExtractionError):
    code = "invalid_encoding"


class CorruptedDocumentError(DocumentExtractionError):
    code = "corrupted_document"


class EncryptedDocumentError(DocumentExtractionError):
    code = "encrypted_document"


class EmptyExtractionError(DocumentExtractionError):
    code = "empty_extraction"


class ExtractionLimitExceededError(DocumentExtractionError):
    code = "limit_exceeded"
