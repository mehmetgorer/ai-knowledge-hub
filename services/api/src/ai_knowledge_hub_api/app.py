from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Knowledge Hub API")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    return application
