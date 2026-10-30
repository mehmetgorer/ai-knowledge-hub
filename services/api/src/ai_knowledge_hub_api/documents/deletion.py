"""Delete owned documents (database, chunks, local storage)."""

import logging

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
    if document.status in _BLOCK_DELETE_STATUSES:
        raise DocumentDeletionConflictError(
            "Document cannot be deleted while processing or indexing",
        )

    storage_key = document.storage_key
    db.delete(document)
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
