"""Typed errors for document text chunking."""


class ChunkingError(Exception):
    code: str = "chunking_failed"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChunkingConfigurationError(ChunkingError):
    code = "invalid_configuration"


class ChunkingLimitExceededError(ChunkingError):
    code = "chunk_limit_exceeded"
