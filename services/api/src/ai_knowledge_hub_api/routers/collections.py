from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.auth.dependencies import get_current_subject
from ai_knowledge_hub_api.db_session import get_db
from ai_knowledge_hub_api.models import Collection
from ai_knowledge_hub_api.schemas import CollectionCreateRequest, CollectionResponse

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
