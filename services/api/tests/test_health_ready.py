from unittest.mock import patch

import httpx
import pytest

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.config import get_settings


@pytest.mark.anyio
async def test_health_ready_returns_200_when_database_is_available() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    with patch(
        "ai_knowledge_hub_api.routers.health.ping_database",
        return_value=True,
    ):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "service": get_settings().service_name,
        "status": "healthy",
        "database": "connected",
    }


@pytest.mark.anyio
async def test_health_ready_returns_503_when_database_is_unavailable() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    with patch(
        "ai_knowledge_hub_api.routers.health.ping_database",
        return_value=False,
    ):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "unavailable"
    assert body["service"] == get_settings().service_name
    assert "password" not in response.text.lower()
