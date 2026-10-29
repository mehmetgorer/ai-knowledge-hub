"""Unit tests for collection ask request validation."""

import pytest
from pydantic import ValidationError

from ai_knowledge_hub_api.schemas import CollectionAskRequest


def test_collection_ask_request_defaults_top_k() -> None:
    body = CollectionAskRequest(question="What is a JOIN?")
    assert body.top_k == 5
    assert body.question == "What is a JOIN?"


def test_collection_ask_request_rejects_empty_question() -> None:
    with pytest.raises(ValidationError):
        CollectionAskRequest(question="   ")


def test_collection_ask_request_rejects_top_k_out_of_range() -> None:
    with pytest.raises(ValidationError):
        CollectionAskRequest(question="x", top_k=0)
    with pytest.raises(ValidationError):
        CollectionAskRequest(question="x", top_k=11)
