from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings
from app.integrations.cognito import decode_cognito_token

security = HTTPBearer()

PLACEHOLDER_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
PLACEHOLDER_TOKEN = "placeholder-access-token"


async def _decode_supabase_jwt(token: str) -> dict:
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
    )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    token = credentials.credentials

    if (settings.use_placeholders or settings.use_local_yolo) and token == PLACEHOLDER_TOKEN:
        return PLACEHOLDER_USER_ID

    try:
        if settings.auth_provider == "cognito" or settings.uses_aws:
            payload = await decode_cognito_token(token)
            cognito_sub = payload.get("sub")
            if not cognito_sub:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
            from app.services import recipe_service

            email = payload.get("email")
            username = payload.get("preferred_username") or payload.get("cognito:username")
            profile = await recipe_service.ensure_profile(cognito_sub, email=email, username=username)
            return profile.id

        if settings.auth_provider == "supabase":
            payload = await _decode_supabase_jwt(token)
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
            return UUID(user_id)

        # Fallback: try Cognito then Supabase
        try:
            payload = await decode_cognito_token(token)
            cognito_sub = payload.get("sub")
            from app.services import recipe_service

            profile = await recipe_service.ensure_profile(
                cognito_sub,
                email=payload.get("email"),
                username=payload.get("preferred_username"),
            )
            return profile.id
        except Exception:
            payload = await _decode_supabase_jwt(token)
            return UUID(payload["sub"])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unable to validate token")


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> UUID | None:
    if credentials is None:
        return None
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None
