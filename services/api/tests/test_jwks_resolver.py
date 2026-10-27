import base64
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jwt.exceptions import PyJWKClientConnectionError

from ai_knowledge_hub_api.auth.errors import AuthenticationError, JwksUnavailableError
from ai_knowledge_hub_api.auth.jwks import PyJwkClientResolver, validate_auth_jwks_url
from tests.auth_keys import TEST_ISSUER, generate_ed25519_key_pair, mint_access_token


def _ed25519_jwk(public_key: object, kid: str) -> dict[str, str]:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    x = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "kid": kid,
        "x": x,
        "alg": "EdDSA",
        "use": "sig",
    }


def _jwks_payload(*keys: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    return {"keys": list(keys)}


def _mint_with_kid(key_pair, kid: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user-rotation",
            "iss": TEST_ISSUER,
            "exp": now + 3600,
            "iat": now,
        },
        key_pair.private_key,
        algorithm="EdDSA",
        headers={"kid": kid},
    )


def test_validate_auth_jwks_url_requires_https_for_remote_hosts() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        validate_auth_jwks_url("http://auth.example.com/.well-known/jwks.json")


def test_validate_auth_jwks_url_allows_local_http() -> None:
    assert (
        validate_auth_jwks_url("http://127.0.0.1:8080/.well-known/jwks.json")
        == "http://127.0.0.1:8080/.well-known/jwks.json"
    )


def test_pyjwk_resolver_valid_signing_key() -> None:
    key_pair = generate_ed25519_key_pair()
    resolver = PyJwkClientResolver(
        "https://jwks.example.test/.well-known/jwks.json",
        cooldown_duration_seconds=0,
    )
    jwks = _jwks_payload(_ed25519_jwk(key_pair.public_key, "kid-a"))
    token = _mint_with_kid(key_pair, "kid-a")

    with patch.object(resolver._client, "fetch_data", return_value=jwks):
        key = resolver.resolve_verification_key(token)

    assert key is not None


def test_pyjwk_resolver_unknown_kid_raises_authentication_error() -> None:
    key_pair = generate_ed25519_key_pair()
    resolver = PyJwkClientResolver(
        "https://jwks.example.test/.well-known/jwks.json",
        cooldown_duration_seconds=0,
    )
    jwks = _jwks_payload(_ed25519_jwk(key_pair.public_key, "other-kid"))
    token = _mint_with_kid(key_pair, "kid-a")

    with patch.object(resolver._client, "fetch_data", return_value=jwks):
        with pytest.raises(AuthenticationError, match="Unknown signing key"):
            resolver.resolve_verification_key(token)


def test_pyjwk_resolver_network_failure_raises_jwks_unavailable() -> None:
    key_pair = generate_ed25519_key_pair()
    resolver = PyJwkClientResolver("https://jwks.example.test/.well-known/jwks.json")
    token = mint_access_token(key_pair)

    with patch.object(
        resolver._client,
        "fetch_data",
        side_effect=PyJWKClientConnectionError("network down"),
    ):
        with pytest.raises(JwksUnavailableError):
            resolver.resolve_verification_key(token)


def test_pyjwk_resolver_retired_key_after_jwks_rotation() -> None:
    key_old = generate_ed25519_key_pair()
    key_new = generate_ed25519_key_pair()
    resolver = PyJwkClientResolver(
        "https://jwks.example.test/.well-known/jwks.json",
        cache_ttl_seconds=1,
        cooldown_duration_seconds=0,
    )
    token_old = _mint_with_kid(key_old, "kid-old")
    jwks_old = _jwks_payload(_ed25519_jwk(key_old.public_key, "kid-old"))
    jwks_new = _jwks_payload(_ed25519_jwk(key_new.public_key, "kid-new"))

    def fetch_jwks():
        if fetch_jwks.calls == 0:
            fetch_jwks.calls += 1
            return jwks_old
        fetch_jwks.calls += 1
        return jwks_new

    fetch_jwks.calls = 0

    with patch.object(resolver._client, "fetch_data", side_effect=fetch_jwks):
        resolver.resolve_verification_key(token_old)
        time.sleep(1.1)
        with pytest.raises(AuthenticationError, match="Unknown signing key"):
            resolver.resolve_verification_key(token_old)
