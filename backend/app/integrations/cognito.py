"""Cognito JWT validation helpers."""

from __future__ import annotations

import time

import httpx
from jose import JWTError, jwk, jwt

from app.config import settings

_jwks_cache: dict | None = None
_jwks_cache_at: float = 0
JWKS_TTL_SECONDS = 3600


def cognito_issuer() -> str:
    if settings.cognito_issuer:
        return settings.cognito_issuer.rstrip("/")
    if settings.cognito_user_pool_id:
        return (
            f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}"
        )
    raise JWTError("Cognito issuer not configured")


async def fetch_cognito_jwks() -> dict:
    global _jwks_cache, _jwks_cache_at
    now = time.time()
    if _jwks_cache and now - _jwks_cache_at < JWKS_TTL_SECONDS:
        return _jwks_cache

    url = f"{cognito_issuer()}/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_at = now
        return _jwks_cache


def signing_key_from_jwks(jwks: dict, kid: str | None):
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key)
    raise JWTError("Signing key not found in JWKS")


async def decode_cognito_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    jwks = await fetch_cognito_jwks()
    key = signing_key_from_jwks(jwks, header.get("kid"))
    return jwt.decode(
        token,
        key,
        algorithms=[header.get("alg", "RS256")],
        audience=settings.cognito_client_id or None,
        issuer=cognito_issuer(),
        options={"verify_aud": bool(settings.cognito_client_id)},
    )
