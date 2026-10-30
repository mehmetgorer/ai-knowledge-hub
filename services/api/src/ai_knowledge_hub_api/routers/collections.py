import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.auth.dependencies import get_current_subject
from ai_knowledge_hub_api.collections.access import get_owned_collection_or_404
from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.db_session import get_db
from ai_knowledge_hub_api.embeddings.errors import EmbeddingInputTooLongError
from ai_knowledge_hub_api.models import Collection
from ai_knowledge_hub_api.rag import (
    RagGroundingError,
    RagOllamaConnectionError,
    RagOllamaError,
    RagOllamaModelError,
    RagOllamaTimeoutError,
    ask_collection_question,
)
from ai_knowledge_hub_api.rag.config import RagConfig
from ai_knowledge_hub_api.schemas import (
    CollectionAskRequest,
    CollectionAskResponse,
    CollectionAskSourceResponse,
    CollectionCreateRequest,
    CollectionResponse,
    CollectionSearchMatchResponse,
    CollectionSearchRequest,
    CollectionSearchResponse,
)
from ai_knowledge_hub_api.search import (
    SearchDatabaseError,
    SearchEmbeddingError,
    semantic_search_collection,
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_collection(
    body: CollectionCreateRequest,
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> Collection:
    collection = Collection(
        owner_subject=owner_subject,
        name=body.name,
    )
    db.add(collection)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(collection)
    return collection


@router.get("", response_model=list[CollectionResponse])
def list_collections(
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> list[Collection]:
    statement = (
        select(Collection)
        .where(Collection.owner_subject == owner_subject)
        .order_by(Collection.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.post(
    "/{collection_id}/search",
    response_model=CollectionSearchResponse,
)
def search_in_collection(
    collection_id: uuid.UUID,
    body: CollectionSearchRequest,
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> CollectionSearchResponse:
    get_owned_collection_or_404(db, collection_id, owner_subject)
    try:
        matches = semantic_search_collection(
            db,
            collection_id=collection_id,
            owner_subject=owner_subject,
            query=body.query,
            top_k=body.top_k,
        )
    except EmbeddingInputTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SearchEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query could not be embedded",
        ) from exc
    except SearchDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        ) from exc

    return CollectionSearchResponse(
        matches=[
            CollectionSearchMatchResponse(
                document_id=match.document_id,
                original_filename=match.original_filename,
                chunk_index=match.chunk_index,
                text=match.text,
                source_kind=match.source_kind,
                page_numbers=list(match.page_numbers),
                cosine_distance=match.cosine_distance,
            )
            for match in matches
        ]
    )


def _rag_config_from_settings(settings: Settings) -> RagConfig:
    return RagConfig(
        max_evidence_passages=min(10, max(1, settings.rag_max_evidence_passages)),
        max_evidence_characters=max(500, settings.rag_max_evidence_characters),
        max_output_tokens=max(64, settings.rag_max_output_tokens),
        weak_retrieval_best_distance_above=(
            settings.rag_weak_retrieval_best_distance_above
        ),
    )


@router.post(
    "/{collection_id}/ask",
    response_model=CollectionAskResponse,
)
def ask_in_collection(
    collection_id: uuid.UUID,
    body: CollectionAskRequest,
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CollectionAskResponse:
    get_owned_collection_or_404(db, collection_id, owner_subject)
    try:
        result = ask_collection_question(
            db,
            collection_id=collection_id,
            owner_subject=owner_subject,
            question=body.question,
            top_k=body.top_k,
            settings=settings,
            rag_config=_rag_config_from_settings(settings),
        )
    except EmbeddingInputTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SearchEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question could not be embedded for retrieval",
        ) from exc
    except SearchDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval is temporarily unavailable",
        ) from exc
    except RagGroundingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer could not be verified as grounded",
        ) from exc
    except (
        RagOllamaConnectionError,
        RagOllamaTimeoutError,
        RagOllamaModelError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local answer generation is unavailable",
        ) from exc
    except RagOllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local answer generation failed",
        ) from exc

    return CollectionAskResponse(
        answer=result.answer,
        sources=[
            CollectionAskSourceResponse(
                source_id=source.source_id,
                document_id=source.document_id,
                original_filename=source.original_filename,
                chunk_index=source.chunk_index,
                page_numbers=list(source.page_numbers),
                text=source.text,
                cosine_distance=source.cosine_distance,
            )
            for source in result.sources
        ],
        model=result.model,
        grounded=result.grounded,
    )
