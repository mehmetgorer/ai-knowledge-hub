import httpx
import pytest

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.config import get_settings
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
async def test_upload_document_requires_authentication(auth_env: None) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    collection_id = "00000000-0000-0000-0000-000000000001"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/collections/{collection_id}/documents",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_list_documents_requires_authentication(auth_env: None) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    collection_id = "00000000-0000-0000-0000-000000000001"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/collections/{collection_id}/documents")
    assert response.status_code == 401


def test_document_response_schema_excludes_storage_key() -> None:
    from ai_knowledge_hub_api.schemas import DocumentResponse

    assert "storage_key" not in DocumentResponse.model_fields
