from fastapi import APIRouter, Depends

from ai_knowledge_hub_api.auth.dependencies import get_current_subject
from ai_knowledge_hub_api.schemas import AuthMeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthMeResponse)
def auth_me(subject: str = Depends(get_current_subject)) -> AuthMeResponse:
    return AuthMeResponse(subject=subject)
