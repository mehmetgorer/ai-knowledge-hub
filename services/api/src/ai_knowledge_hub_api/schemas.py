from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_knowledge_hub_api.models import DocumentStatus


class HealthLiveResponse(BaseModel):
    service: str
    status: Literal["healthy"]


class HealthReadyResponse(BaseModel):
    service: str
    status: Literal["healthy", "unavailable"]
    database: Literal["connected", "unavailable"]


class AuthMeResponse(BaseModel):
    subject: str


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_must_be_non_empty_after_strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    content_hash_sha256: str | None
    created_at: datetime
    updated_at: datetime


class DocumentProcessResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    chunk_count: int
