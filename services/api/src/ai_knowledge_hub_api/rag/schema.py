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
        "support_quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "minLength": 1},
                    "quote": {"type": "string", "minLength": 8},
                },
                "required": ["source_id", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "answer",
        "evidence_sufficient",
        "cited_source_ids",
        "support_quotes",
    ],
    "additionalProperties": False,
}
