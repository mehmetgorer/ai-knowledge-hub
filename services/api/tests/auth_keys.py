"""Ed25519 test keys for JWT authentication tests."""

import time
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

TEST_ISSUER = "https://auth.example.test/"
TEST_JWKS_URL = "https://auth.example.test/.well-known/jwks.json"
TEST_KID = "test-ed25519-key"


@dataclass(frozen=True)
class Ed25519KeyPair:
    private_key: Ed25519PrivateKey
    public_key: object
    kid: str = TEST_KID


def generate_ed25519_key_pair() -> Ed25519KeyPair:
    private_key = Ed25519PrivateKey.generate()
    return Ed25519KeyPair(
        private_key=private_key,
        public_key=private_key.public_key(),
    )


def mint_access_token(
    key_pair: Ed25519KeyPair,
    *,
    subject: str = "neon-auth|user-123",
    issuer: str = TEST_ISSUER,
    expires_in_seconds: int = 3600,
    issued_at: int | None = None,
    not_before: int | None = None,
    extra_claims: dict[str, object] | None = None,
    signing_key: Ed25519PrivateKey | None = None,
    algorithm: str = "EdDSA",
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": subject,
        "iss": issuer,
        "exp": now + expires_in_seconds,
        "iat": issued_at if issued_at is not None else now,
    }
    if not_before is not None:
        payload["nbf"] = not_before
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        signing_key or key_pair.private_key,
        algorithm=algorithm,
        headers={"kid": key_pair.kid},
    )
