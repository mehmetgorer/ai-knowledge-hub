import httpx
import pytest
from pydantic import ValidationError

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.schemas import CollectionCreateRequest
from tests.auth_keys import TEST_ISSUER, TEST_JWKS_URL


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("AUTH_AUDIENCE", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_create_collection_requires_authentication(auth_env: None) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/collections", json={"name": "Notes"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_list_collections_requires_authentication(auth_env: None) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/collections")
    assert response.status_code == 401


def test_create_collection_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="")


def test_create_collection_rejects_whitespace_name() -> None:
    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="   ")


def test_create_collection_strips_name() -> None:
    model = CollectionCreateRequest(name="  Research  ")
    assert model.name == "Research"


def test_create_request_schema_excludes_owner_subject() -> None:
    assert "owner_subject" not in CollectionCreateRequest.model_fields
