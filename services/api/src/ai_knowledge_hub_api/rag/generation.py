"""Generate, validate, and optionally repair one grounded model response."""

import logging
from collections.abc import Callable
from dataclasses import replace

from ai_knowledge_hub_api.rag import validation_codes as codes
from ai_knowledge_hub_api.rag.errors import (
    RagGroundingError,
    RagOllamaResponseError,
)
from ai_knowledge_hub_api.rag.ollama import OllamaChatRequest
from ai_knowledge_hub_api.rag.parse_completion import parse_structured_completion
from ai_knowledge_hub_api.rag.repair import build_repair_user_message
from ai_knowledge_hub_api.rag.validation import (
    ValidatedAnswer,
    validate_grounded_answer,
)

logger = logging.getLogger(__name__)

GenerateJsonCompletionFn = Callable[[OllamaChatRequest], str]


def complete_and_validate_grounded_answer(
    generate_fn: GenerateJsonCompletionFn,
    chat_request: OllamaChatRequest,
    *,
    allowed_source_ids: frozenset[str],
) -> ValidatedAnswer:
    allowed_tuple = tuple(sorted(allowed_source_ids))
    first_failure_code: str | None = None

    for attempt_index in range(2):
        request = chat_request
        if attempt_index == 1 and first_failure_code is not None:
            repair_user = build_repair_user_message(
                chat_request.user_message,
                validation_code=first_failure_code,
                allowed_source_ids=allowed_tuple,
            )
            request = replace(chat_request, user_message=repair_user)

        raw_content = generate_fn(request)
        try:
            payload = parse_structured_completion(raw_content)
            validated = validate_grounded_answer(
                payload,
                allowed_source_ids=allowed_source_ids,
            )
        except RagGroundingError as exc:
            logger.warning(
                "RAG answer validation failed code=%s attempt=%s",
                exc.code,
                attempt_index + 1,
            )
            if attempt_index == 0:
                first_failure_code = exc.code
                continue
            raise
        except RagOllamaResponseError as exc:
            raise RagGroundingError(
                "Model response could not be verified",
                code=codes.MALFORMED_JSON,
            ) from exc

        if attempt_index == 1 and first_failure_code is not None:
            logger.info(
                "RAG answer validation repaired after code=%s",
                first_failure_code,
            )
        return validated

    raise RagGroundingError(
        "Model response could not be verified",
        code=first_failure_code or "validation_failed",
    )
