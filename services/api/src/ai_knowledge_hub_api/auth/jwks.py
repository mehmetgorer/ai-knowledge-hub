from typing import Protocol
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from ai_knowledge_hub_api.auth.errors import AuthenticationError, JwksUnavailableError

ALLOWED_JWT_ALGORITHM = "EdDSA"
_LOCAL_JWKS_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_auth_jwks_url(url: str) -> str:
    """Require HTTPS for remote JWKS endpoints (local dev may use HTTP)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("AUTH_JWKS_URL must use http or https")
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and hostname not in _LOCAL_JWKS_HOSTS:
        raise ValueError("AUTH_JWKS_URL must use HTTPS outside local development")
    return url


def _map_pyjwk_client_error(exc: PyJWKClientError) -> Exception:
    if isinstance(exc, PyJWKClientConnectionError):
        return JwksUnavailableError("JWKS endpoint unavailable")

    message = str(exc)
    if "Unable to find a signing key" in message:
        return AuthenticationError("Unknown signing key")
    if "did not contain any signing keys" in message:
        return AuthenticationError("Unknown signing key")

    return JwksUnavailableError("JWKS endpoint unavailable")


class JwksKeyResolver(Protocol):
    def resolve_verification_key(self, token: str) -> object:
        """Return a public key suitable for ``jwt.decode``."""
        ...


class PyJwkClientResolver:
    """Fetch signing keys from a JWKS endpoint with bounded JWK-set caching."""

    def __init__(
        self,
        jwks_url: str,
        *,
        cache_ttl_seconds: float = 300.0,
        request_timeout_seconds: float = 10.0,
        cooldown_duration_seconds: float = 0.0,
    ) -> None:
        validate_auth_jwks_url(jwks_url)
        self._client = PyJWKClient(
            jwks_url,
            cache_keys=False,
            cache_jwk_set=True,
            lifespan=int(cache_ttl_seconds),
            timeout=int(request_timeout_seconds),
            cooldown_duration=cooldown_duration_seconds,
        )

    def resolve_verification_key(self, token: str) -> object:
        try:
            return self._client.get_signing_key_from_jwt(token).key
        except PyJWKClientError as exc:
            raise _map_pyjwk_client_error(exc) from exc


class StaticJwksResolver:
    """Test resolver mapping ``kid`` headers to verification keys."""

    def __init__(self, keys_by_kid: dict[str, object]) -> None:
        self._keys_by_kid = keys_by_kid

    def resolve_verification_key(self, token: str) -> object:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or kid not in self._keys_by_kid:
            raise AuthenticationError("Unknown signing key")
        return self._keys_by_kid[kid]
