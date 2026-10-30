"""JSON Schema for Ollama structured grounded answers."""

GROUNDED_ANSWER_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "evidence_sufficient": {"type": "boolean"},
        "cited_source_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "required": ["answer", "evidence_sufficient", "cited_source_ids"],
    "additionalProperties": False,
}
