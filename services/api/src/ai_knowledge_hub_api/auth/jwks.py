from typing import Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from ai_knowledge_hub_api.auth.errors import AuthenticationError, JwksUnavailableError

ALLOWED_JWT_ALGORITHM = "EdDSA"


class JwksKeyResolver(Protocol):
    def resolve_verification_key(self, token: str) -> object:
        """Return a public key suitable for ``jwt.decode``."""
        ...


class PyJwkClientResolver:
    """Fetch signing keys from a JWKS endpoint with caching."""

    def __init__(
        self,
        jwks_url: str,
        *,
        cache_ttl_seconds: float = 300.0,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        self._client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=int(cache_ttl_seconds),
            timeout=int(request_timeout_seconds),
        )

    def resolve_verification_key(self, token: str) -> object:
        try:
            return self._client.get_signing_key_from_jwt(token).key
        except PyJWKClientError as exc:
            raise JwksUnavailableError("JWKS endpoint unavailable") from exc


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
