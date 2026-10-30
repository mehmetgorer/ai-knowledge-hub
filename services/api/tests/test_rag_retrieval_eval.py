"""
Deterministic retrieval metrics on synthetic indexed chunks (mocked embeddings).

Uses orthogonal basis vectors so nearest neighbors are exact without a real model.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.models import (
    Collection,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from ai_knowledge_hub_api.search.service import semantic_search_collection
from tests.test_semantic_search_integration import (
    _CONFIG,
    _MODEL,
    _basis_vector,
)

pytest_plugins = ["tests.test_semantic_search_integration"]


def _recall_at_k(
    relevant_chunk_indices: set[int],
    retrieved: list[int],
    k: int,
) -> float:
    top = retrieved[:k]
    if not relevant_chunk_indices:
        return 1.0 if not top else 0.0
    hits = sum(1 for index in top if index in relevant_chunk_indices)
    return hits / len(relevant_chunk_indices)


def _mrr(relevant_chunk_indices: set[int], retrieved: list[int]) -> float:
    for rank, index in enumerate(retrieved, start=1):
        if index in relevant_chunk_indices:
            return 1.0 / rank
    return 0.0


@pytest.mark.integration
def test_synthetic_retrieval_recall_and_mrr_with_basis_vectors(
    auth_env: None,
    migrated_search_database: str,
) -> None:
    del auth_env, migrated_search_database
    settings = get_settings()
    engine = create_engine(settings.resolved_database_url)
    target_chunk_index = 2
    decoy_indices = (0, 1, 3, 4)

    with Session(engine) as session:
        collection = Collection(owner_subject="eval|owner", name="Eval")
        session.add(collection)
        session.flush()
        document = Document(
            collection_id=collection.id,
            original_filename="synthetic.txt",
            mime_type="text/plain",
            size_bytes=10,
            storage_key=f"documents/{collection.id}/{uuid.uuid4()}",
            status=DocumentStatus.READY,
        )
        session.add(document)
        session.flush()
        for index in (*decoy_indices, target_chunk_index):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=f"chunk-{index}",
                    source_kind="text",
                    page_numbers=[index + 1],
                    character_count=8,
                    embedding=_basis_vector(index),
                    embedding_model=_MODEL,
                    embedded_at=datetime.now(UTC),
                ),
            )
        session.commit()
        collection_id = collection.id

    def embed_query_for_target(_text: str, *, config=None) -> list[float]:
        del config
        return _basis_vector(target_chunk_index)

    with patch(
        "ai_knowledge_hub_api.search.service.embed_search_query",
        side_effect=embed_query_for_target,
    ):
        with Session(engine) as session:
            matches = semantic_search_collection(
                session,
                collection_id=collection_id,
                owner_subject="eval|owner",
                query="target phrase",
                top_k=5,
                config=_CONFIG,
            )

    retrieved_indices = [match.chunk_index for match in matches]
    relevant = {target_chunk_index}
    recall3 = _recall_at_k(relevant, retrieved_indices, k=3)
    recall5 = _recall_at_k(relevant, retrieved_indices, k=5)
    mrr = _mrr(relevant, retrieved_indices)

    assert recall3 == 1.0
    assert recall5 == 1.0
    assert mrr == 1.0
    assert retrieved_indices[0] == target_chunk_index
