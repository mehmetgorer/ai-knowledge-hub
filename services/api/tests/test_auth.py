import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.auth.dependencies import get_jwks_resolver
from ai_knowledge_hub_api.auth.errors import (
    AuthenticationConfigurationError,
    JwksUnavailableError,
)
from ai_knowledge_hub_api.auth.jwks import StaticJwksResolver
from ai_knowledge_hub_api.auth.verifier import verify_access_token
from ai_knowledge_hub_api.config import Settings, get_settings
from tests.auth_keys import (
    TEST_ISSUER,
    TEST_JWKS_URL,
    Ed25519KeyPair,
    generate_ed25519_key_pair,
    mint_access_token,
)


class _UnavailableResolver:
    def resolve_verification_key(self, token: str) -> object:
        raise JwksUnavailableError("JWKS down")


@pytest.fixture
def key_pair() -> Ed25519KeyPair:
    return generate_ed25519_key_pair()


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def authed_client(
    auth_env: None,
    key_pair: Ed25519KeyPair,
):
    app = create_app()
    app.dependency_overrides[get_jwks_resolver] = lambda: StaticJwksResolver(
        {key_pair.kid: key_pair.public_key}
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_auth_me_returns_verified_subject(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    token = mint_access_token(key_pair, subject="neon-auth|verified-user")
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"subject": "neon-auth|verified-user"}
    assert "token" not in response.text.lower()


@pytest.mark.anyio
async def test_auth_me_missing_token_returns_401(
    authed_client: httpx.AsyncClient,
) -> None:
    response = await authed_client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_invalid_signature_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    other = Ed25519PrivateKey.generate()
    token = mint_access_token(key_pair, signing_key=other)
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_expired_token_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    token = mint_access_token(key_pair, expires_in_seconds=-60)
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_wrong_issuer_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    token = mint_access_token(key_pair, issuer="https://wrong-issuer.test/")
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_missing_subject_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    now = int(time.time())
    token = jwt.encode(
        {"iss": TEST_ISSUER, "exp": now + 3600, "iat": now},
        key_pair.private_key,
        algorithm="EdDSA",
        headers={"kid": key_pair.kid},
    )
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_empty_subject_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    token = mint_access_token(key_pair, subject="   ")
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_unsupported_algorithm_returns_401(
    authed_client: httpx.AsyncClient,
    key_pair: Ed25519KeyPair,
) -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user",
            "iss": TEST_ISSUER,
            "exp": now + 3600,
            "iat": now,
        },
        "not-eddsa",
        algorithm="HS256",
        headers={"kid": key_pair.kid},
    )
    response = await authed_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_me_missing_configuration_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_JWKS_URL", raising=False)
    monkeypatch.delenv("AUTH_ISSUER", raising=False)
    get_settings.cache_clear()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer dummy"},
        )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_auth_me_jwks_unavailable_returns_503(
    auth_env: None,
    key_pair: Ed25519KeyPair,
) -> None:
    app = create_app()
    app.dependency_overrides[get_jwks_resolver] = lambda: _UnavailableResolver()
    token = mint_access_token(key_pair)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_health_endpoints_remain_public_without_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_JWKS_URL", raising=False)
    monkeypatch.delenv("AUTH_ISSUER", raising=False)
    get_settings.cache_clear()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
    assert live.status_code == 200
    assert ready.status_code in {200, 503}


def test_require_auth_configuration_fails_when_incomplete() -> None:
    settings = Settings(auth_jwks_url=TEST_JWKS_URL, auth_issuer=None)
    with pytest.raises(AuthenticationConfigurationError):
        settings.require_auth_configuration()


def test_verify_access_token_returns_subject(
    key_pair: Ed25519KeyPair,
    auth_env: None,
) -> None:
    settings = Settings()
    token = mint_access_token(key_pair, subject="trusted-subject")
    subject = verify_access_token(
        token,
        settings,
        StaticJwksResolver({key_pair.kid: key_pair.public_key}),
    )
    assert subject == "trusted-subject"
