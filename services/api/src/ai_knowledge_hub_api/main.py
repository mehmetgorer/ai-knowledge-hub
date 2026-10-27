import uvicorn

from ai_knowledge_hub_api.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "ai_knowledge_hub_api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
    )
