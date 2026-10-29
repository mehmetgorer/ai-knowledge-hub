"""Typed errors for local embedding inference."""


class EmbeddingError(Exception):
    code: str = "embedding_failed"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyEmbeddingInputError(EmbeddingError):
    code = "empty_input"


class InvalidEmbeddingQueryError(EmbeddingError):
    code = "invalid_query"


class EmbeddingInputTooLongError(EmbeddingError):
    code = "input_too_long"

    def __init__(
        self,
        message: str,
        *,
        token_count: int,
        max_tokens: int,
        character_count: int,
        input_kind: str,
    ) -> None:
        super().__init__(message)
        self.token_count = token_count
        self.max_tokens = max_tokens
        self.character_count = character_count
        self.input_kind = input_kind


class EmbeddingInferenceError(EmbeddingError):
    code = "inference_failed"


class InvalidEmbeddingVectorError(EmbeddingError):
    code = "invalid_vector"
