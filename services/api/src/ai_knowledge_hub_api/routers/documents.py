import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_knowledge_hub_api.auth.dependencies import get_current_subject
from ai_knowledge_hub_api.collections.access import get_owned_collection_or_404
from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.db_session import get_db
from ai_knowledge_hub_api.documents.validation import (
    DocumentUploadValidationError,
    generate_storage_key,
    validate_upload_content,
)
from ai_knowledge_hub_api.models import Document, DocumentStatus
from ai_knowledge_hub_api.schemas import DocumentResponse
from ai_knowledge_hub_api.storage.dependencies import get_document_storage
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage

router = APIRouter(prefix="/collections", tags=["documents"])


async def _read_upload_with_limit(
    upload: UploadFile,
    max_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 64)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum upload size",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/{collection_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    collection_id: uuid.UUID,
    file: UploadFile = File(...),
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: LocalDocumentStorage = Depends(get_document_storage),
) -> Document:
    get_owned_collection_or_404(db, collection_id, owner_subject)

    raw = await _read_upload_with_limit(file, settings.document_max_upload_bytes)
    try:
        validated = validate_upload_content(
            filename=file.filename,
            data=raw,
            max_bytes=settings.document_max_upload_bytes,
        )
    except DocumentUploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    storage_key = generate_storage_key(collection_id)
    storage.write(storage_key, validated.content)

    document = Document(
        collection_id=collection_id,
        original_filename=validated.original_filename,
        mime_type=validated.mime_type,
        size_bytes=len(validated.content),
        storage_key=storage_key,
        status=DocumentStatus.UPLOADED,
        content_hash_sha256=validated.content_hash_sha256,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise
    db.refresh(document)
    return document


@router.get(
    "/{collection_id}/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    collection_id: uuid.UUID,
    owner_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> list[Document]:
    get_owned_collection_or_404(db, collection_id, owner_subject)
    statement = (
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(statement).all())
