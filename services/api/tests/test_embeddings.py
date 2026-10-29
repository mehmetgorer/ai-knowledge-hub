import math

import numpy as np
import pytest

from ai_knowledge_hub_api.embeddings import (
    DEFAULT_EMBEDDING_CONFIG,
    EmbeddingConfig,
    EmbeddingInferenceError,
    EmbeddingInputTooLongError,
    EmptyEmbeddingInputError,
    embed_document_chunks,
    embed_search_query,
    reset_embedding_runtime,
    set_embedding_runtime_loader,
    validate_embedding_vector,
)


class _MockTokenizer:
    def __init__(self, *, tokens_per_char: float = 0.2) -> None:
        self.tokens_per_char = tokens_per_char
        self.last_encoded: list[str] = []

    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        del add_special_tokens
        self.last_encoded.append(text)
        count = max(1, int(math.ceil(len(text) * self.tokens_per_char)))
        return list(range(count))


class _MockModel:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        self.encode_calls: list[tuple[list[str], dict]] = []

    def encode(
        self,
        sentences,
        *,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    ):
        del batch_size, show_progress_bar
        if isinstance(sentences, str):
            batch = [sentences]
        else:
            batch = list(sentences)
        self.encode_calls.append(
            (batch, {"normalize_embeddings": normalize_embeddings})
        )
        rows = []
        for index, _sentence in enumerate(batch):
            rng = np.random.default_rng(index + len(batch))
            vector = rng.standard_normal(self.dim)
            if normalize_embeddings:
                vector = vector / np.linalg.norm(vector)
            rows.append(vector)
        if convert_to_numpy:
            return np.stack(rows, axis=0)
        return rows


def _install_mock_runtime(
    *,
    dim: int = 384,
    tokens_per_char: float = 0.2,
) -> tuple[_MockModel, _MockTokenizer, list[int]]:
    load_counts: list[int] = []
    model = _MockModel(dim=dim)
    tokenizer = _MockTokenizer(tokens_per_char=tokens_per_char)

    class _Runtime:
        pass

    runtime = _Runtime()
    runtime.model = model
    runtime.tokenizer = tokenizer

    def loader(_config: EmbeddingConfig) -> _Runtime:
        load_counts.append(1)
        return runtime

    reset_embedding_runtime()
    set_embedding_runtime_loader(loader)
    return model, tokenizer, load_counts


@pytest.fixture(autouse=True)
def _reset_embedding_state() -> None:
    reset_embedding_runtime()
    set_embedding_runtime_loader(None)
    yield
    reset_embedding_runtime()
    set_embedding_runtime_loader(None)


def test_embed_search_query_uses_query_prefix_and_returns_384_dims() -> None:
    model, tokenizer, _ = _install_mock_runtime()
    vector = embed_search_query("What is RAG?")
    assert len(vector) == 384
    assert tokenizer.last_encoded[-1].startswith("query: ")
    assert model.encode_calls[-1][0] == ["query: What is RAG?"]


def test_embed_document_chunks_uses_passage_prefix_and_preserves_order() -> None:
    model, _, _ = _install_mock_runtime()
    chunks = ["First chunk.", "Second chunk."]
    vectors = embed_document_chunks(chunks)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert model.encode_calls[-1][0] == [
        "passage: First chunk.",
        "passage: Second chunk.",
    ]
    validate_embedding_vector(vectors[0])
    validate_embedding_vector(vectors[1])


def test_embed_document_chunks_rejects_empty_chunk() -> None:
    _install_mock_runtime()
    with pytest.raises(EmptyEmbeddingInputError):
        embed_document_chunks(["valid", "   "])


def test_embed_search_query_rejects_empty_query() -> None:
    _install_mock_runtime()
    with pytest.raises(EmptyEmbeddingInputError):
        embed_search_query("   ")


def test_token_limit_raises_without_calling_encode() -> None:
    model, _, _ = _install_mock_runtime(tokens_per_char=1.0)
    long_text = "x" * 600
    with pytest.raises(EmbeddingInputTooLongError) as exc_info:
        embed_document_chunks([long_text])
    assert exc_info.value.token_count > DEFAULT_EMBEDDING_CONFIG.max_input_tokens
    assert exc_info.value.character_count == len(
        f"{DEFAULT_EMBEDDING_CONFIG.passage_prefix}{long_text}"
    )
    assert model.encode_calls == []


def test_validate_embedding_vector_rejects_wrong_dimension() -> None:
    with pytest.raises(Exception, match="384 dimensions"):
        validate_embedding_vector([0.0] * 10)


def test_validate_embedding_vector_rejects_non_normalized_vector() -> None:
    vector = [1.0] * 384
    with pytest.raises(Exception, match="not L2-normalized"):
        validate_embedding_vector(vector)


def test_runtime_loader_is_reused_across_calls() -> None:
    _, _, load_counts = _install_mock_runtime()
    embed_search_query("hello")
    embed_search_query("world")
    assert load_counts == [1]


def test_turkish_and_english_samples_embed_with_prefixes() -> None:
    model, tokenizer, _ = _install_mock_runtime()
    tr = embed_search_query("İstanbul hakkında bilgi")
    en = embed_document_chunks(["English paragraph about embeddings."])[0]
    assert len(tr) == 384
    assert len(en) == 384
    assert any(text.startswith("query: ") for text in tokenizer.last_encoded)
    assert any(text.startswith("passage: ") for text in model.encode_calls[-1][0])


def test_inference_errors_are_wrapped() -> None:
    model, _, _ = _install_mock_runtime()

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated failure")

    model.encode = boom  # type: ignore[method-assign]
    with pytest.raises(EmbeddingInferenceError):
        embed_search_query("fail please")
