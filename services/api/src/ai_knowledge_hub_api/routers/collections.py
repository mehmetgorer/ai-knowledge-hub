import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.auth.dependencies import get_current_subject
from ai_knowledge_hub_api.collections.access import get_owned_collection_or_404
from ai_knowledge_hub_api.db_session import get_db
from ai_knowledge_hub_api.embeddings.errors import EmbeddingInputTooLongError
from ai_knowledge_hub_api.models import Collection
from ai_knowledge_hub_api.schemas import (
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
