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


class DocumentIndexResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    embedding_model: str
    embedded_chunk_count: int


class CollectionSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_must_be_non_empty_after_strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class CollectionSearchMatchResponse(BaseModel):
    document_id: UUID
    original_filename: str
    chunk_index: int
    text: str
    source_kind: str
    page_numbers: list[int]
    cosine_distance: float


class CollectionSearchResponse(BaseModel):
    matches: list[CollectionSearchMatchResponse]


class CollectionAskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def question_must_be_non_empty_after_strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty")
        return stripped


class CollectionAskSourceResponse(BaseModel):
    source_id: str
    document_id: UUID
    original_filename: str
    chunk_index: int
    page_numbers: list[int]
    text: str
    cosine_distance: float


class CollectionAskResponse(BaseModel):
    answer: str
    sources: list[CollectionAskSourceResponse]
    model: str
    grounded: bool
