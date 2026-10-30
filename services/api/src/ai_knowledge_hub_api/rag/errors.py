"""Domain errors for grounded RAG answer generation."""


class RagError(Exception):
    """Base class for RAG pipeline errors."""


class RagValidationError(RagError):
    """Invalid question or request parameters."""


class RagGroundingError(RagError):
    """Model output failed citation or grounding validation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class RagFailClosedAbstention(RagError):
    """Model output cannot be shown; return safe server abstention."""

    def __init__(self, *, code: str) -> None:
        super().__init__("Answer withheld pending source support")
        self.code = code


class RagGenerationError(RagError):
    """Answer generation failed for a non-grounding reason."""


class RagOllamaError(RagGenerationError):
    """Ollama request failed."""


class RagOllamaConnectionError(RagOllamaError):
    """Could not connect to the local Ollama server."""


class RagOllamaTimeoutError(RagOllamaError):
    """Ollama request timed out."""


class RagOllamaModelError(RagOllamaError):
    """Requested model is missing or not loadable."""


class RagOllamaResponseError(RagOllamaError):
    """Ollama returned an unexpected or malformed payload."""
