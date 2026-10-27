from fastapi import APIRouter, Response

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.database import ping_database
from ai_knowledge_hub_api.schemas import HealthLiveResponse, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
def health_live() -> HealthLiveResponse:
    settings = get_settings()
    return HealthLiveResponse(service=settings.service_name, status="healthy")


@router.get("/ready", response_model=HealthReadyResponse)
def health_ready(response: Response) -> HealthReadyResponse:
    settings = get_settings()
    if ping_database():
        return HealthReadyResponse(
            service=settings.service_name,
            status="healthy",
            database="connected",
        )

    response.status_code = 503
    return HealthReadyResponse(
        service=settings.service_name,
        status="unavailable",
        database="unavailable",
    )
