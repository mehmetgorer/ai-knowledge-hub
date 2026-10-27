from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.database import dispose_engine
from ai_knowledge_hub_api.routers import auth, health


@asynccontextmanager
async def lifespan(_application: FastAPI):
    yield
    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Knowledge Hub API", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(auth.router)
    return application
