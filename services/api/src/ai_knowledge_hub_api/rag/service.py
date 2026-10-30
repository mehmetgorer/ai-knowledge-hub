"""Collection-scoped grounded RAG orchestration."""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.rag.config import RagConfig
from ai_knowledge_hub_api.rag.errors import (
    RagGroundingError,
    RagOllamaError,
    RagOllamaResponseError,
)
from ai_knowledge_hub_api.rag.evidence import EvidenceSource, build_evidence_context
from ai_knowledge_hub_api.rag.ollama import (
    OllamaChatClient,
    OllamaChatRequest,
    get_default_ollama_client,
)
from ai_knowledge_hub_api.rag.prompts import (
    build_system_instructions,
    build_user_message,
)
from ai_knowledge_hub_api.rag.relevance import should_abstain_for_weak_retrieval
from ai_knowledge_hub_api.rag.validation import (
    ValidatedAnswer,
    parse_structured_completion,
    validate_grounded_answer,
)
from ai_knowledge_hub_api.search.service import (
    EmbedQueryFn,
    semantic_search_collection,
)

logger = logging.getLogger(__name__)

GenerateJsonCompletionFn = Callable[[OllamaChatRequest], str]

DEFAULT_RAG_CONFIG = RagConfig()


@dataclass(frozen=True, slots=True)
class AskSource:
    source_id: str
    document_id: uuid.UUID
    original_filename: str
    chunk_index: int
    page_numbers: tuple[int, ...]
    text: str
    cosine_distance: float


@dataclass(frozen=True, slots=True)
class AskCollectionResult:
    answer: str
    sources: tuple[AskSource, ...]
    model: str
    grounded: bool


def _no_evidence_answer(question: str) -> str:
    normalized = question.strip()
    if any("\u0400" <= char <= "\u04ff" for char in normalized):
        return (
            "Seçili koleksiyonda bu soruyu yanıtlamak için yeterli kaynak bulunamadı."
        )
    if any("\u0600" <= char <= "\u06ff" for char in normalized):
        return "لم أجد مصادر كافية في المجموعة المحددة للإجابة على هذا السؤال."
    # Basic Turkish detection (common letters)
    lower = normalized.casefold()
    turkish_hints = ("ğ", "ı", "ş", "ç", "ö", "ü", " ve ", " bir ", " nedir")
    if any(hint in lower for hint in turkish_hints):
        return (
            "Seçili koleksiyonda bu soruyu yanıtlamak için yeterli kaynak bulunamadı."
        )
    return (
        "No sufficient sources were found in the selected collection to answer "
        "this question."
    )


def _sources_for_citations(
    evidence: list[EvidenceSource],
    cited_ids: tuple[str, ...],
) -> tuple[AskSource, ...]:
    by_id = {item.source_id: item for item in evidence}
    result: list[AskSource] = []
    for source_id in cited_ids:
        item = by_id.get(source_id)
        if item is None:
            continue
        match = item.match
        result.append(
            AskSource(
                source_id=source_id,
                document_id=match.document_id,
                original_filename=match.original_filename,
                chunk_index=match.chunk_index,
                page_numbers=match.page_numbers,
                text=match.text,
                cosine_distance=match.cosine_distance,
            )
        )
    return tuple(result)


def ask_collection_question(
    db: Session,
    *,
    collection_id: uuid.UUID,
    owner_subject: str,
    question: str,
    top_k: int,
    settings: Settings | None = None,
    rag_config: RagConfig | None = None,
    embed_query: EmbedQueryFn | None = None,
    ollama_client: OllamaChatClient | None = None,
    generate_json: GenerateJsonCompletionFn | None = None,
) -> AskCollectionResult:
    resolved_settings = settings or get_settings()
    resolved_rag = rag_config or DEFAULT_RAG_CONFIG
    effective_top_k = min(top_k, resolved_rag.max_evidence_passages)

    matches = semantic_search_collection(
        db,
        collection_id=collection_id,
        owner_subject=owner_subject,
        query=question,
        top_k=effective_top_k,
        embed_query=embed_query,
    )

    evidence = build_evidence_context(matches, config=resolved_rag)
    model_name = resolved_settings.ollama_model

    if not evidence:
        db.commit()
        return AskCollectionResult(
            answer=_no_evidence_answer(question),
            sources=(),
            model=model_name,
            grounded=False,
        )

    if should_abstain_for_weak_retrieval(
        evidence,
        weak_best_distance_above=resolved_rag.weak_retrieval_best_distance_above,
    ):
        db.commit()
        return AskCollectionResult(
            answer=_no_evidence_answer(question),
            sources=(),
            model=model_name,
            grounded=False,
        )

    db.commit()
    if db.in_transaction():
        logger.warning(
            "RAG generation starting while DB session still in transaction "
            "collection_id=%s",
            collection_id,
        )

    system_message = build_system_instructions()
    user_message = build_user_message(question=question, sources=evidence)
    chat_request = OllamaChatRequest(
        model=model_name,
        system_message=system_message,
        user_message=user_message,
        max_output_tokens=resolved_rag.max_output_tokens,
        timeout_seconds=resolved_settings.ollama_request_timeout_seconds,
        base_url=resolved_settings.ollama_base_url,
        temperature=resolved_settings.ollama_temperature,
        think_enabled=resolved_settings.ollama_think_enabled,
    )

    client = ollama_client or get_default_ollama_client()
    generate_fn = generate_json or client.complete_json

    try:
        raw_content = generate_fn(chat_request)
    except RagOllamaError:
        raise

    try:
        payload = parse_structured_completion(raw_content)
        allowed = frozenset(item.source_id for item in evidence)
        validated = validate_grounded_answer(
            payload,
            allowed_source_ids=allowed,
        )
    except RagGroundingError:
        raise
    except RagOllamaResponseError as exc:
        raise RagGroundingError("Model response could not be verified") from exc

    if not validated.grounded:
        return AskCollectionResult(
            answer=validated.answer,
            sources=(),
            model=model_name,
            grounded=False,
        )

    return AskCollectionResult(
        answer=validated.answer,
        sources=_sources_for_citations(evidence, validated.cited_source_ids),
        model=model_name,
        grounded=True,
    )


def apply_validated_answer_for_tests(
    payload: dict[str, object],
    evidence: list[EvidenceSource],
) -> ValidatedAnswer:
    """Expose validation for unit tests."""
    allowed = frozenset(item.source_id for item in evidence)
    return validate_grounded_answer(
        payload,
        allowed_source_ids=allowed,
    )
