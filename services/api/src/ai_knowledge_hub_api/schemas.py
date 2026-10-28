from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
