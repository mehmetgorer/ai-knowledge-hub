import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.collections.access import get_owned_collection_or_404
from ai_knowledge_hub_api.models import Document


def get_owned_document_or_404(
    db: Session,
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    owner_subject: str,
) -> Document:
    get_owned_collection_or_404(db, collection_id, owner_subject)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document
