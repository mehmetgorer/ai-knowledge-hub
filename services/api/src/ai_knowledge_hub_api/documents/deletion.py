"""Delete owned documents (database, chunks, local storage)."""

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.models import Document, DocumentStatus
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage

logger = logging.getLogger(__name__)

_BLOCK_DELETE_STATUSES = frozenset(
    {
        DocumentStatus.PROCESSING,
        DocumentStatus.INDEXING,
    }
)


class DocumentDeletionConflictError(Exception):
    """Document cannot be deleted in its current lifecycle state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def delete_owned_document(
    db: Session,
    *,
    document: Document,
    storage: LocalDocumentStorage,
) -> None:
    """
    Delete the document row atomically (status guard in SQL), then remove storage.

    Uses a conditional DELETE so a stale ORM instance cannot remove a row that
    moved to PROCESSING/INDEXING after the HTTP handler loaded the document.
    """
    document_id: uuid.UUID = document.id
    result = db.execute(
        delete(Document)
        .where(
            Document.id == document_id,
            Document.status.not_in(_BLOCK_DELETE_STATUSES),
        )
        .returning(Document.storage_key)
    )
    row = result.first()
    if row is None:
        db.rollback()
        current_status = db.scalar(
            select(Document.status).where(Document.id == document_id)
        )
        if current_status is None:
            return
        if current_status in _BLOCK_DELETE_STATUSES:
            raise DocumentDeletionConflictError(
                "Document cannot be deleted while processing or indexing",
            )
        raise DocumentDeletionConflictError(
            "Document cannot be deleted in its current lifecycle state",
        )

    storage_key = row[0]
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        storage.delete(storage_key)
    except OSError:
        logger.warning(
            "Document storage object could not be removed after database delete "
            "(orphan file may remain on disk)",
        )
