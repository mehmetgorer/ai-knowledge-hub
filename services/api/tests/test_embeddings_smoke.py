"""Optional real-model smoke test (downloads weights; not run in default CI)."""

import os

import pytest

from ai_knowledge_hub_api.embeddings import (
    embed_document_chunks,
    embed_search_query,
    reset_embedding_runtime,
    set_embedding_runtime_loader,
    validate_embedding_vector,
)


@pytest.mark.embedding_smoke
def test_real_multilingual_e5_small_smoke() -> None:
    if os.environ.get("RUN_EMBEDDING_SMOKE") != "1":
        pytest.skip("Set RUN_EMBEDDING_SMOKE=1 to download and run the real model")

    reset_embedding_runtime()
    set_embedding_runtime_loader(None)

    query = embed_search_query("What is a knowledge base?")
    passages = embed_document_chunks(
        [
            "English passage about semantic search.",
            "Türkçe: anlamsal arama ve vektörler.",
        ]
    )
    assert len(query) == 384
    assert len(passages) == 2
    validate_embedding_vector(query)
    validate_embedding_vector(passages[0])
    validate_embedding_vector(passages[1])
