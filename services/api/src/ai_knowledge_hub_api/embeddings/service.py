import math
import threading
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import numpy as np

from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import (
    EmbeddingInferenceError,
    EmbeddingInputTooLongError,
    EmptyEmbeddingInputError,
    InvalidEmbeddingQueryError,
    InvalidEmbeddingVectorError,
)

DEFAULT_EMBEDDING_CONFIG = EmbeddingConfig()


class SupportsEncode(Protocol):
    def encode(
        self,
        sentences: Sequence[str] | str,
        *,
        batch_size: int = ...,
        normalize_embeddings: bool = ...,
        show_progress_bar: bool = ...,
        convert_to_numpy: bool = ...,
    ) -> Any: ...


class SupportsTokenize(Protocol):
    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = ...,
    ) -> list[int]: ...


class EmbeddingRuntime(Protocol):
    model: SupportsEncode
    tokenizer: SupportsTokenize


_model_lock = threading.Lock()
_cached_runtime: EmbeddingRuntime | None = None
_cached_config_key: tuple[str, int] | None = None
_runtime_loader: Callable[[EmbeddingConfig], EmbeddingRuntime] | None = None


def set_embedding_runtime_loader(
    loader: Callable[[EmbeddingConfig], EmbeddingRuntime] | None,
) -> None:
    """Test hook: inject a mock runtime loader."""
    global _runtime_loader, _cached_runtime, _cached_config_key
    with _model_lock:
        _runtime_loader = loader
        _cached_runtime = None
        _cached_config_key = None


def reset_embedding_runtime() -> None:
    global _cached_runtime, _cached_config_key
    with _model_lock:
        _cached_runtime = None
        _cached_config_key = None


def _default_runtime_loader(config: EmbeddingConfig) -> EmbeddingRuntime:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(config.model_name)
    model.max_seq_length = config.max_input_tokens
    return _SentenceTransformerRuntime(model)


class _SentenceTransformerRuntime:
    def __init__(self, model: SupportsEncode) -> None:
        self.model = model
        self.tokenizer = model.tokenizer  # type: ignore[attr-defined]


def _get_runtime(config: EmbeddingConfig) -> EmbeddingRuntime:
    global _cached_runtime, _cached_config_key
    key = (config.model_name, config.max_input_tokens)
    if _cached_runtime is not None and _cached_config_key == key:
        return _cached_runtime

    with _model_lock:
        if _cached_runtime is not None and _cached_config_key == key:
            return _cached_runtime
        loader = _runtime_loader or _default_runtime_loader
        _cached_runtime = loader(config)
        _cached_config_key = key
        return _cached_runtime


def count_input_tokens(text: str, runtime: EmbeddingRuntime) -> int:
    tokens = runtime.tokenizer.encode(text, add_special_tokens=True)
    return len(tokens)


def validate_input_token_length(
    text: str,
    *,
    runtime: EmbeddingRuntime,
    config: EmbeddingConfig,
    input_kind: str,
) -> None:
    token_count = count_input_tokens(text, runtime)
    if token_count > config.max_input_tokens:
        raise EmbeddingInputTooLongError(
            f"{input_kind} exceeds model token limit "
            f"({token_count} tokens > {config.max_input_tokens} max)",
            token_count=token_count,
            max_tokens=config.max_input_tokens,
            character_count=len(text),
            input_kind=input_kind,
        )


def embed_document_chunks(
    chunks: Sequence[str],
    *,
    config: EmbeddingConfig | None = None,
) -> list[list[float]]:
    """
    Embed passage-prefixed document chunks in order (batched).

    Character-based chunks must already fit the model token limit; oversized
    inputs raise EmbeddingInputTooLongError (no silent truncation).
    """
    resolved = config or DEFAULT_EMBEDDING_CONFIG
    if not chunks:
        return []

    runtime = _get_runtime(resolved)
    prefixed: list[str] = []
    for index, chunk in enumerate(chunks):
        if not chunk or not chunk.strip():
            raise EmptyEmbeddingInputError(
                f"Chunk at index {index} is empty and cannot be embedded"
            )
        text = f"{resolved.passage_prefix}{chunk}"
        validate_input_token_length(
            text,
            runtime=runtime,
            config=resolved,
            input_kind=f"passage[{index}]",
        )
        prefixed.append(text)

    try:
        vectors = runtime.model.encode(
            prefixed,
            batch_size=resolved.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
    except Exception as exc:
        raise EmbeddingInferenceError("Passage embedding inference failed") from exc

    np_vectors = np.asarray(vectors)
    if np_vectors.ndim != 2:
        raise EmbeddingInferenceError("Unexpected embedding output shape")

    results: list[list[float]] = []
    for index in range(np_vectors.shape[0]):
        row = np_vectors[index].tolist()
        validate_embedding_vector(row, expected_dimensions=resolved.expected_dimensions)
        results.append(row)
    return results


def embed_search_query(
    query: str,
    *,
    config: EmbeddingConfig | None = None,
) -> list[float]:
    """Embed a single query-prefixed search string."""
    resolved = config or DEFAULT_EMBEDDING_CONFIG
    if query is None:
        raise InvalidEmbeddingQueryError("Query must be a string")
    if not query.strip():
        raise EmptyEmbeddingInputError("Query must be non-empty")

    runtime = _get_runtime(resolved)
    text = f"{resolved.query_prefix}{query.strip()}"
    validate_input_token_length(
        text,
        runtime=runtime,
        config=resolved,
        input_kind="query",
    )

    try:
        vector = runtime.model.encode(
            text,
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
    except Exception as exc:
        raise EmbeddingInferenceError("Query embedding inference failed") from exc

    np_vector = np.asarray(vector)
    if np_vector.ndim == 2:
        np_vector = np_vector[0]
    row = np_vector.tolist()
    validate_embedding_vector(row, expected_dimensions=resolved.expected_dimensions)
    return row


def validate_embedding_vector(
    vector: Sequence[float],
    *,
    expected_dimensions: int = DEFAULT_EMBEDDING_CONFIG.expected_dimensions,
) -> None:
    if len(vector) != expected_dimensions:
        raise InvalidEmbeddingVectorError(
            f"Expected {expected_dimensions} dimensions, got {len(vector)}"
        )
    for value in vector:
        if not math.isfinite(float(value)):
            raise InvalidEmbeddingVectorError("Embedding contains non-finite values")
    norm = math.sqrt(sum(float(value) * float(value) for value in vector))
    if norm == 0.0:
        raise InvalidEmbeddingVectorError("Embedding vector has zero norm")
    if not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
        raise InvalidEmbeddingVectorError(
            f"Embedding is not L2-normalized (norm={norm:.6f})"
        )
