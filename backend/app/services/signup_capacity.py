"""Enforce a hard cap on total user creations (private beta)."""

from __future__ import annotations

import json
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

LEDGER_PATH = Path(settings.uploads_dir).parent / "signup_ledger.json"


def _read_ledger() -> list[str]:
    if not LEDGER_PATH.exists():
        return []
    try:
        data = json.loads(LEDGER_PATH.read_text())
        emails = data.get("emails", [])
        return [e.lower().strip() for e in emails if isinstance(e, str) and e.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _write_ledger(emails: list[str]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    unique = sorted({e.lower().strip() for e in emails if e.strip()})
    LEDGER_PATH.write_text(json.dumps({"emails": unique}, indent=2))


def ledger_count() -> int:
    return len(_read_ledger())


def ledger_has(email: str) -> bool:
    return email.lower().strip() in _read_ledger()


def ledger_add(email: str) -> None:
    emails = _read_ledger()
    key = email.lower().strip()
    if key not in emails:
        emails.append(key)
        _write_ledger(emails)


def count_cognito_users() -> int | None:
    """Return Cognito user count, or None if pool unset / AWS unavailable."""
    pool_id = settings.cognito_user_pool_id.strip()
    if not pool_id:
        return None
    try:
        client = boto3.client("cognito-idp", region_name=settings.aws_region)
        count = 0
        token = None
        while True:
            kwargs: dict = {"UserPoolId": pool_id, "Limit": 60}
            if token:
                kwargs["PaginationToken"] = token
            resp = client.list_users(**kwargs)
            count += len(resp.get("Users", []))
            token = resp.get("PaginationToken")
            if not token:
                break
        return count
    except (BotoCoreError, ClientError, Exception):
        return None


async def count_db_profiles() -> int | None:
    if not settings.uses_db:
        return None
    try:
        from app.db.pool import get_pool

        pool = await get_pool()
        return int(await pool.fetchval("SELECT COUNT(*) FROM profiles") or 0)
    except Exception:
        return None


async def current_user_count() -> int:
    """Authoritative creation count: Cognito → DB profiles → local ledger."""
    cognito = count_cognito_users()
    if cognito is not None:
        return cognito
    db = await count_db_profiles()
    if db is not None:
        return db
    return ledger_count()


async def signup_status() -> dict:
    limit = settings.max_users
    count = await current_user_count()
    remaining = max(0, limit - count)
    return {
        "limit": limit,
        "count": count,
        "remaining": remaining,
        "open": remaining > 0,
    }


def create_cognito_user(email: str, password: str, username: str) -> None:
    pool_id = settings.cognito_user_pool_id.strip()
    if not pool_id:
        raise RuntimeError("Cognito user pool is not configured")
    client = boto3.client("cognito-idp", region_name=settings.aws_region)
    try:
        client.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "preferred_username", "Value": username},
            ],
            MessageAction="SUPPRESS",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "UsernameExistsException":
            raise
        # Existing user (e.g. stuck FORCE_CHANGE_PASSWORD) — still set permanent password below.
    client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=email,
        Password=password,
        Permanent=True,
    )


def validate_password_policy(password: str) -> str | None:
    """Return an error message if password fails Cognito pool defaults, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return "Password must include an uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must include a lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must include a number"
    return None
