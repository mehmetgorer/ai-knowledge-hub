import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.models import Collection


def get_owned_collection_or_404(
    db: Session,
    collection_id: uuid.UUID,
    owner_subject: str,
) -> Collection:
    collection = db.scalar(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.owner_subject == owner_subject,
        )
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    return collection
