from fastapi import APIRouter

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.schemas import HealthLiveResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
def health_live() -> HealthLiveResponse:
    settings = get_settings()
    return HealthLiveResponse(service=settings.service_name, status="healthy")
