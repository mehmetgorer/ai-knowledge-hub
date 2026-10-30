"""Parse model JSON completions (including common formatting drift)."""

import json
import re

from ai_knowledge_hub_api.rag.errors import RagOllamaResponseError

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def extract_json_text(raw_content: str) -> str:
    stripped = raw_content.strip()
    if not stripped:
        raise RagOllamaResponseError("Empty model response")
    fence = _JSON_FENCE.search(stripped)
    if fence:
        return fence.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def parse_structured_completion(raw_content: str) -> dict[str, object]:
    json_text = extract_json_text(raw_content)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RagOllamaResponseError("Model response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RagOllamaResponseError("Model response JSON must be an object")
    return payload
