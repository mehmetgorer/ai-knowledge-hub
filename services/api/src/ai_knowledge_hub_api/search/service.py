"""Collection-scoped semantic search over indexed document chunks."""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.embeddings.config import EmbeddingConfig
from ai_knowledge_hub_api.embeddings.errors import (
    EmbeddingError,
    EmbeddingInputTooLongError,
)
from ai_knowledge_hub_api.embeddings.service import (
    DEFAULT_EMBEDDING_CONFIG,
    embed_search_query,
)
from ai_knowledge_hub_api.models import (
    Collection,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from ai_knowledge_hub_api.search.errors import (
    SearchDatabaseError,
    SearchEmbeddingError,
)

logger = logging.getLogger(__name__)

EmbedQueryFn = Callable[[str, EmbeddingConfig], list[float]]


@dataclass(frozen=True, slots=True)
class SemanticSearchMatch:
    document_id: uuid.UUID
    original_filename: str
    chunk_index: int
    text: str
    source_kind: str
    page_numbers: tuple[int, ...]
    cosine_distance: float


def semantic_search_collection(
    db: Session,
    *,
    collection_id: uuid.UUID,
    owner_subject: str,
    query: str,
    top_k: int,
    config: EmbeddingConfig | None = None,
    embed_query: EmbedQueryFn | None = None,
) -> list[SemanticSearchMatch]:
    """
    Embed the query outside a long DB transaction, then rank chunks in PostgreSQL.
    """
    resolved = config or DEFAULT_EMBEDDING_CONFIG
    normalized_query = query.strip()
    embed_fn = embed_query or _default_embed_query

    db.commit()

    try:
        query_vector = embed_fn(normalized_query, resolved)
    except EmbeddingInputTooLongError:
        raise
    except EmbeddingError as exc:
        logger.warning(
            "Search query embedding failed collection_id=%s code=%s",
            collection_id,
            getattr(exc, "code", type(exc).__name__),
        )
        raise SearchEmbeddingError("Search query embedding failed") from exc
    except Exception as exc:
        logger.warning(
            "Search query embedding failed collection_id=%s error_type=%s",
            collection_id,
            type(exc).__name__,
        )
        raise SearchEmbeddingError("Search query embedding failed") from exc

    distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)

    statement = (
        select(
            Document.id.label("document_id"),
            Document.original_filename.label("original_filename"),
            DocumentChunk.chunk_index.label("chunk_index"),
            DocumentChunk.text.label("text"),
            DocumentChunk.source_kind.label("source_kind"),
            DocumentChunk.page_numbers.label("page_numbers"),
            distance_expr.label("cosine_distance"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(Collection, Document.collection_id == Collection.id)
        .where(
            Collection.id == collection_id,
            Collection.owner_subject == owner_subject,
            Document.status == DocumentStatus.READY,
            DocumentChunk.embedding.isnot(None),
            DocumentChunk.embedding_model == resolved.model_name,
        )
        .order_by(
            distance_expr.asc(),
            Document.id.asc(),
            DocumentChunk.chunk_index.asc(),
        )
        .limit(top_k)
    )

    try:
        rows = db.execute(statement).all()
    except Exception as exc:
        logger.warning(
            "Semantic search query failed collection_id=%s error_type=%s",
            collection_id,
            type(exc).__name__,
        )
        raise SearchDatabaseError("Search could not be completed") from exc

    matches: list[SemanticSearchMatch] = []
    for row in rows:
        page_numbers = row.page_numbers or []
        matches.append(
            SemanticSearchMatch(
                document_id=row.document_id,
                original_filename=row.original_filename,
                chunk_index=row.chunk_index,
                text=row.text,
                source_kind=row.source_kind,
                page_numbers=tuple(int(value) for value in page_numbers),
                cosine_distance=float(row.cosine_distance),
            )
        )
    return matches


def _default_embed_query(text: str, config: EmbeddingConfig) -> list[float]:
    return embed_search_query(text, config=config)
