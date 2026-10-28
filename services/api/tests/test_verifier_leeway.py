"""JWT clock skew leeway tests for verify_access_token."""

import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai_knowledge_hub_api.auth.errors import AuthenticationError
from ai_knowledge_hub_api.auth.jwks import StaticJwksResolver
from ai_knowledge_hub_api.auth.verifier import (
    JWT_CLOCK_SKEW_LEEWAY_SECONDS,
    verify_access_token,
)
from ai_knowledge_hub_api.config import Settings, get_settings
from tests.auth_keys import (
    TEST_ISSUER,
    TEST_JWKS_URL,
    Ed25519KeyPair,
    generate_ed25519_key_pair,
    mint_access_token,
)


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("AUTH_AUDIENCE", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def key_pair() -> Ed25519KeyPair:
    return generate_ed25519_key_pair()


@pytest.fixture
def auth_settings(auth_env: None) -> Settings:
    return Settings(
        auth_jwks_url=TEST_JWKS_URL,
        auth_issuer=TEST_ISSUER,
        auth_audience=None,
    )


def test_accepts_iat_about_three_tenths_second_in_future(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    now = time.time()
    issued_at = int(now + 0.3)
    token = mint_access_token(
        key_pair,
        issued_at=issued_at,
        expires_in_seconds=3600,
    )
    subject = verify_access_token(
        token,
        auth_settings,
        StaticJwksResolver({key_pair.kid: key_pair.public_key}),
    )
    assert subject == "neon-auth|user-123"


def test_rejects_iat_more_than_leeway_seconds_in_future(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    issued_at = int(time.time()) + JWT_CLOCK_SKEW_LEEWAY_SECONDS + 1
    token = mint_access_token(
        key_pair,
        issued_at=issued_at,
        expires_in_seconds=3600,
    )
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            auth_settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )


def test_rejects_nbf_more_than_leeway_seconds_in_future(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    not_before = int(time.time()) + JWT_CLOCK_SKEW_LEEWAY_SECONDS + 1
    token = mint_access_token(
        key_pair,
        not_before=not_before,
        expires_in_seconds=3600,
    )
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            auth_settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )


def test_rejects_expired_token_beyond_leeway(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    token = mint_access_token(
        key_pair,
        expires_in_seconds=-(JWT_CLOCK_SKEW_LEEWAY_SECONDS + 1),
    )
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            auth_settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )


def test_rejects_invalid_signature(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    other = Ed25519PrivateKey.generate()
    token = mint_access_token(key_pair, signing_key=other)
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            auth_settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )


def test_rejects_wrong_issuer(
    key_pair: Ed25519KeyPair,
    auth_settings: Settings,
) -> None:
    token = mint_access_token(key_pair, issuer="https://wrong-issuer.test/")
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            auth_settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )


def test_rejects_wrong_audience_when_configured(
    key_pair: Ed25519KeyPair,
) -> None:
    settings = Settings(
        auth_jwks_url=TEST_JWKS_URL,
        auth_issuer=TEST_ISSUER,
        auth_audience="expected-audience",
    )

    token = mint_access_token(
        key_pair,
        extra_claims={"aud": "wrong-audience"},
    )
    with pytest.raises(AuthenticationError, match="Token verification failed"):
        verify_access_token(
            token,
            settings,
            StaticJwksResolver({key_pair.kid: key_pair.public_key}),
        )
