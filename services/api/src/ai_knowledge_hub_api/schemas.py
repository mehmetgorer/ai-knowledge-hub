from typing import Literal

from pydantic import BaseModel


class HealthLiveResponse(BaseModel):
    service: str
    status: Literal["healthy"]
