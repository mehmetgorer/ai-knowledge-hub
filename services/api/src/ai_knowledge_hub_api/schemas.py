from typing import Literal

from pydantic import BaseModel


class HealthLiveResponse(BaseModel):
    service: str
    status: Literal["healthy"]


class HealthReadyResponse(BaseModel):
    service: str
    status: Literal["healthy", "unavailable"]
    database: Literal["connected", "unavailable"]


class AuthMeResponse(BaseModel):
    subject: str
