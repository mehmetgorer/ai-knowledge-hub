"""Unit tests for document indexing helpers (no database)."""

import math

from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig


def _mock_embed(texts, config: EmbeddingConfig) -> list[list[float]]:
    del config
    scale = 1.0 / math.sqrt(384)
    return [[scale] * 384 for _ in texts]


def test_mock_embed_produces_normalized_384_vectors() -> None:
    config = EmbeddingConfig()
    vectors = _mock_embed(["alpha", "beta"], config)
    assert len(vectors) == 2
    assert len(vectors[0]) == config.expected_dimensions
    norm = math.sqrt(sum(value * value for value in vectors[0]))
    assert math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4)
