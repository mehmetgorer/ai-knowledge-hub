import jwt

from ai_knowledge_hub_api.auth.errors import AuthenticationError
from ai_knowledge_hub_api.auth.jwks import ALLOWED_JWT_ALGORITHM, JwksKeyResolver
from ai_knowledge_hub_api.config import Settings

# Tolerates small issuer/client clock skew (Neon JWT iat can be ~0.3s ahead).
JWT_CLOCK_SKEW_LEEWAY_SECONDS = 5


def verify_access_token(
    token: str,
    settings: Settings,
    jwks_resolver: JwksKeyResolver,
) -> str:
    """Verify a JWT and return the trusted subject (``sub`` claim)."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token header") from exc

    algorithm = header.get("alg")
    if algorithm != ALLOWED_JWT_ALGORITHM:
        raise AuthenticationError("Unsupported token algorithm")

    verification_key = jwks_resolver.resolve_verification_key(token)

    decode_kwargs: dict[str, object] = {
        "algorithms": [ALLOWED_JWT_ALGORITHM],
        "issuer": settings.auth_issuer,
        "leeway": JWT_CLOCK_SKEW_LEEWAY_SECONDS,
        "options": {
            "require": ["sub", "exp", "iss"],
            "verify_aud": bool(settings.auth_audience),
        },
    }
    if settings.auth_audience:
        decode_kwargs["audience"] = settings.auth_audience

    try:
        payload = jwt.decode(token, verification_key, **decode_kwargs)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token verification failed") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("Missing subject claim")

    return subject.strip()
