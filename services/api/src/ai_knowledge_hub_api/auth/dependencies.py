from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ai_knowledge_hub_api.auth.errors import (
    AuthenticationConfigurationError,
    AuthenticationError,
    JwksUnavailableError,
)
from ai_knowledge_hub_api.auth.jwks import JwksKeyResolver, PyJwkClientResolver
from ai_knowledge_hub_api.auth.verifier import verify_access_token
from ai_knowledge_hub_api.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_resolver_for_url(
    jwks_url: str,
    cache_ttl_seconds: float,
    request_timeout_seconds: float,
) -> PyJwkClientResolver:
    return PyJwkClientResolver(
        jwks_url,
        cache_ttl_seconds=cache_ttl_seconds,
        request_timeout_seconds=request_timeout_seconds,
    )


def get_jwks_resolver(settings: Settings = Depends(get_settings)) -> JwksKeyResolver:
    try:
        settings.require_auth_configuration()
    except AuthenticationConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None

    assert settings.auth_jwks_url is not None
    return _jwks_resolver_for_url(
        settings.auth_jwks_url,
        settings.auth_jwks_cache_ttl_seconds,
        settings.auth_jwks_request_timeout_seconds,
    )


def clear_jwks_resolver_cache() -> None:
    _jwks_resolver_for_url.cache_clear()


def get_current_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    jwks_resolver: JwksKeyResolver = Depends(get_jwks_resolver),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return verify_access_token(credentials.credentials, settings, jwks_resolver)
    except JwksUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication keys unavailable",
        ) from None
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
