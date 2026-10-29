"""Unit tests for semantic search request validation."""

import pytest
from pydantic import ValidationError

from ai_knowledge_hub_api.schemas import CollectionSearchRequest


def test_collection_search_request_defaults_top_k() -> None:
    body = CollectionSearchRequest(query="hello")
    assert body.top_k == 5
    assert body.query == "hello"


def test_collection_search_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        CollectionSearchRequest(query="   ")


def test_collection_search_request_rejects_top_k_out_of_range() -> None:
    with pytest.raises(ValidationError):
        CollectionSearchRequest(query="x", top_k=0)
    with pytest.raises(ValidationError):
        CollectionSearchRequest(query="x", top_k=11)
