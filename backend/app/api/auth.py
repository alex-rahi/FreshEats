from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.services import signup_capacity

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    username: str = Field(..., min_length=2, max_length=40)


@router.get("/signup-status")
async def get_signup_status():
    return await signup_capacity.signup_status()


@router.post("/register")
async def register(body: RegisterBody):
    """Create a beta user if under the hard cap (default 5)."""
    status_info = await signup_capacity.signup_status()
    email = body.email.lower().strip()
    username = body.username.strip()
    if "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Valid email required")

    pw_err = signup_capacity.validate_password_policy(body.password)
    if pw_err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=pw_err)

    already = signup_capacity.ledger_has(email)
    if not status_info["open"] and not already:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"Private beta is full ({status_info['limit']} users max).",
        )

    use_cognito = (
        settings.auth_provider == "cognito"
        and bool(settings.cognito_user_pool_id.strip())
        and not settings.use_placeholders
        and not settings.use_local_yolo
    )

    if use_cognito:
        from botocore.exceptions import ClientError

        before = signup_capacity.count_cognito_users() or 0
        try:
            signup_capacity.create_cognito_user(email, body.password, username)
        except ClientError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=e.response.get("Error", {}).get("Message") or str(e),
            ) from e
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        after = signup_capacity.count_cognito_users()
        # New user pushed past the cap — roll back
        if after is not None and before < settings.max_users and after > settings.max_users:
            try:
                client = __import__("boto3").client(
                    "cognito-idp", region_name=settings.aws_region
                )
                client.admin_delete_user(
                    UserPoolId=settings.cognito_user_pool_id, Username=email
                )
            except Exception:
                pass
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Private beta is full ({settings.max_users} users max).",
            )

        signup_capacity.ledger_add(email)
        return {
            "ok": True,
            "mode": "cognito",
            "email": email,
            **(await signup_capacity.signup_status()),
        }

    if not already:
        if signup_capacity.ledger_count() >= settings.max_users:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Private beta is full ({settings.max_users} users max).",
            )
        signup_capacity.ledger_add(email)

    return {
        "ok": True,
        "mode": "demo",
        "email": email,
        **(await signup_capacity.signup_status()),
    }
