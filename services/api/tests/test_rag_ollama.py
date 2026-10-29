"""Unit tests for Ollama HTTP client error mapping."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from ai_knowledge_hub_api.rag.errors import (
    RagOllamaConnectionError,
    RagOllamaModelError,
    RagOllamaResponseError,
    RagOllamaTimeoutError,
)
from ai_knowledge_hub_api.rag.ollama import HttpOllamaChatClient, OllamaChatRequest


def _request() -> OllamaChatRequest:
    return OllamaChatRequest(
        model="qwen3:1.7b",
        system_message="sys",
        user_message="user",
        max_output_tokens=64,
        timeout_seconds=1.0,
        base_url="http://127.0.0.1:11434",
    )


def test_ollama_client_maps_timeout() -> None:
    client = HttpOllamaChatClient()
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("slow")):
        with pytest.raises(RagOllamaTimeoutError):
            client.complete_json(_request())


def test_ollama_client_maps_connection_error() -> None:
    client = HttpOllamaChatClient()
    with patch(
        "httpx.Client.post",
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises(RagOllamaConnectionError):
            client.complete_json(_request())


def test_ollama_client_maps_missing_model() -> None:
    client = HttpOllamaChatClient()
    response = MagicMock()
    response.status_code = 404
    with patch("httpx.Client.post", return_value=response):
        with pytest.raises(RagOllamaModelError):
            client.complete_json(_request())


def test_ollama_client_returns_message_content() -> None:
    client = HttpOllamaChatClient()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "message": {"content": '{"answer":"hi","cited_source_ids":[]}'}
    }
    with patch("httpx.Client.post", return_value=response):
        content = client.complete_json(_request())
    assert "hi" in content


def test_ollama_client_rejects_missing_content() -> None:
    client = HttpOllamaChatClient()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"message": {}}
    with patch("httpx.Client.post", return_value=response):
        with pytest.raises(RagOllamaResponseError):
            client.complete_json(_request())
