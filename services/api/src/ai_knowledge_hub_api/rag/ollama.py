"""Local Ollama HTTP client (server-side endpoint only)."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from ai_knowledge_hub_api.rag.errors import (
    RagOllamaConnectionError,
    RagOllamaModelError,
    RagOllamaResponseError,
    RagOllamaTimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OllamaChatRequest:
    model: str
    system_message: str
    user_message: str
    max_output_tokens: int
    timeout_seconds: float
    base_url: str
    temperature: float = 0.0
    think_enabled: bool = False


class OllamaChatClient(Protocol):
    def complete_json(self, request: OllamaChatRequest) -> str: ...


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


class HttpOllamaChatClient:
    """Calls Ollama /api/chat with JSON format (non-streaming)."""

    def complete_json(self, request: OllamaChatRequest) -> str:
        url = f"{_normalize_base_url(request.base_url)}/api/chat"
        body: dict[str, object] = {
            "model": request.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": request.system_message},
                {"role": "user", "content": request.user_message},
            ],
            "options": {
                "num_predict": request.max_output_tokens,
                "temperature": request.temperature,
            },
        }
        if not request.think_enabled:
            body["think"] = False
        try:
            with httpx.Client(timeout=request.timeout_seconds) as client:
                response = client.post(url, json=body)
        except httpx.TimeoutException as exc:
            logger.warning("Ollama request timed out model=%s", request.model)
            raise RagOllamaTimeoutError("Local model request timed out") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Ollama connection failed error_type=%s",
                type(exc).__name__,
            )
            raise RagOllamaConnectionError(
                "Local model server is unavailable",
            ) from exc

        if response.status_code == 404:
            raise RagOllamaModelError("Requested local model is not available")
        if response.status_code >= 400:
            raise RagOllamaResponseError("Local model server rejected the request")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RagOllamaResponseError("Local model returned invalid JSON") from exc

        message = payload.get("message")
        if not isinstance(message, dict):
            raise RagOllamaResponseError("Local model response missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise RagOllamaResponseError("Local model response missing content")
        return content


_DEFAULT_CLIENT = HttpOllamaChatClient()


def get_default_ollama_client() -> OllamaChatClient:
    return _DEFAULT_CLIENT
