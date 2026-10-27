import httpx
import pytest

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.config import get_settings


@pytest.mark.anyio
async def test_health_live_returns_healthy_status() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "service": get_settings().service_name,
        "status": "healthy",
    }
