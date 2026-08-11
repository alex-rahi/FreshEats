"""RDS-backed recipe / social / profile services."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg

from app.db.pool import get_pool
from app.integrations import s3 as s3_store
from app.integrations import sqs as sqs_queue
from app.models.schemas import (
    CommentResponse,
    RecipeCreate,
    RecipeImage,
    RecipeResponse,
    RecipeStatus,
    UserProfile,
)
from app.config import settings


def _profile_from_row(row) -> UserProfile:
    return UserProfile(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        avatar_url=row["avatar_url"],
        bio=row["bio"],
        recipe_count=row["recipe_count"] or 0,
        created_at=row["created_at"],
    )


async def ensure_profile(cognito_sub: str, email: str | None = None, username: str | None = None) -> UserProfile:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM profiles WHERE cognito_sub = $1", cognito_sub)
        if row:
            return _profile_from_row(row)
        uname = username or (email.split("@")[0] if email else f"cook_{cognito_sub[:8]}")
        row = await conn.fetchrow(
            """
            INSERT INTO profiles (id, cognito_sub, username, display_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (cognito_sub) DO UPDATE SET updated_at = NOW()
            RETURNING *
            """,
            uuid4(),
            cognito_sub,
            uname,
            uname,
        )
        return _profile_from_row(row)


async def get_profile(profile_id: UUID) -> UserProfile | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM profiles WHERE id = $1", profile_id)
    return _profile_from_row(row) if row else None


async def update_profile(profile_id: UUID, **fields) -> UserProfile:
    allowed = {k: v for k, v in fields.items() if k in {"username", "display_name", "bio", "avatar_url"} and v is not None}
    if not allowed:
        profile = await get_profile(profile_id)
        if not profile:
            raise ValueError("Profile not found")
        return profile
    sets = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(allowed))
    values = list(allowed.values())
    pool = await get_pool()
    row = await pool.fetchrow(
        f"UPDATE profiles SET {sets}, updated_at = NOW() WHERE id = $1 RETURNING *",
        profile_id,
        *values,
    )
    return _profile_from_row(row)


async def _recipe_from_row(row, author: UserProfile | None, liked: bool = False) -> RecipeResponse:
    images = []
    if row.get("storage_path"):
        images.append(
            RecipeImage(
                storage_path=row["storage_path"],
                public_url=row.get("public_url"),
                is_primary=True,
            )
        )
    return RecipeResponse(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        moderation_decision=row.get("moderation_decision"),
        moderation_reason=row.get("moderation_reason"),
        like_count=row["like_count"] or 0,
        comment_count=row["comment_count"] or 0,
        liked_by_me=liked,
        image_url=row.get("public_url"),
        images=images,
        author=author,
        created_at=row["created_at"],
    )


async def create_recipe(user_id: UUID, body: RecipeCreate) -> dict:
    """Create recipe + image placeholder + return upload info."""
    pool = await get_pool()
    recipe_id = uuid4()
    storage_path = f"{user_id}/{recipe_id}.jpg"
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO recipes (id, user_id, title, description, status)
                VALUES ($1, $2, $3, $4, 'uploading')
                RETURNING *
                """,
                recipe_id,
                user_id,
                body.title,
                body.description,
            )
            await conn.execute(
                """
                INSERT INTO recipe_images (recipe_id, storage_path, is_primary)
                VALUES ($1, $2, TRUE)
                """,
                recipe_id,
                storage_path,
            )
            job = await conn.fetchrow(
                """
                INSERT INTO moderation_jobs (recipe_id, status, current_step)
                VALUES ($1, 'queued', 'awaiting_upload')
                RETURNING id
                """,
                recipe_id,
            )
    author = await get_profile(user_id)
    recipe = await _recipe_from_row({**dict(row), "storage_path": storage_path, "public_url": None}, author)
    upload_url = s3_store.presign_put(settings.storage_bucket_raw, storage_path)
    return {"recipe": recipe, "upload_url": upload_url, "storage_path": storage_path, "job_id": str(job["id"])}


async def confirm_upload(recipe_id: UUID, user_id: UUID) -> RecipeResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM recipes WHERE id = $1", recipe_id)
        if not row or row["user_id"] != user_id:
            raise LookupError("Recipe not found")
        img = await conn.fetchrow(
            "SELECT * FROM recipe_images WHERE recipe_id = $1 ORDER BY sort_order LIMIT 1",
            recipe_id,
        )
        storage_path = img["storage_path"]
        public = s3_store.public_url(storage_path.replace(f"{user_id}/", "") if False else storage_path)
        # Prefer copying to recipes bucket path same key
        try:
            s3_store.copy_object(
                settings.storage_bucket_raw,
                storage_path,
                settings.storage_bucket_recipes,
                storage_path,
            )
            public = s3_store.public_url(storage_path)
        except Exception:
            public = s3_store.public_url(storage_path)

        await conn.execute(
            "UPDATE recipe_images SET public_url = $2 WHERE id = $1",
            img["id"],
            public,
        )
        await conn.execute(
            "UPDATE recipes SET status = 'processing', updated_at = NOW() WHERE id = $1",
            recipe_id,
        )
        job = await conn.fetchrow(
            """
            UPDATE moderation_jobs
            SET current_step = 'queued_for_worker', status = 'queued'
            WHERE recipe_id = $1
            RETURNING id
            """,
            recipe_id,
        )
        message_id = sqs_queue.enqueue_moderation(str(recipe_id), storage_path, str(job["id"]) if job else None)
        if job:
            await conn.execute(
                "UPDATE moderation_jobs SET sqs_message_id = $2 WHERE id = $1",
                job["id"],
                message_id,
            )
        updated = await conn.fetchrow(
            """
            SELECT r.*, ri.storage_path, ri.public_url
            FROM recipes r
            LEFT JOIN recipe_images ri ON ri.recipe_id = r.id AND ri.is_primary
            WHERE r.id = $1
            """,
            recipe_id,
        )
    author = await get_profile(user_id)
    return await _recipe_from_row(dict(updated), author)


async def list_published(viewer_id: UUID | None = None, limit: int = 30) -> list[RecipeResponse]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT r.*, ri.storage_path, ri.public_url,
               p.username, p.display_name, p.avatar_url, p.bio, p.recipe_count, p.created_at AS author_created
        FROM recipes r
        JOIN profiles p ON p.id = r.user_id
        LEFT JOIN recipe_images ri ON ri.recipe_id = r.id AND ri.is_primary
        WHERE r.status = 'published'
        ORDER BY r.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    liked_ids: set[UUID] = set()
    if viewer_id and rows:
        liked = await pool.fetch(
            "SELECT recipe_id FROM likes WHERE user_id = $1 AND recipe_id = ANY($2::uuid[])",
            viewer_id,
            [r["id"] for r in rows],
        )
        liked_ids = {x["recipe_id"] for x in liked}

    result = []
    for row in rows:
        author = UserProfile(
            id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            avatar_url=row["avatar_url"],
            bio=row["bio"],
            recipe_count=row["recipe_count"] or 0,
            created_at=row["author_created"],
        )
        result.append(await _recipe_from_row(dict(row), author, liked=row["id"] in liked_ids))
    return result


async def get_recipe(recipe_id: UUID, viewer_id: UUID | None = None) -> RecipeResponse | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT r.*, ri.storage_path, ri.public_url,
               p.username, p.display_name, p.avatar_url, p.bio, p.recipe_count, p.created_at AS author_created
        FROM recipes r
        JOIN profiles p ON p.id = r.user_id
        LEFT JOIN recipe_images ri ON ri.recipe_id = r.id AND ri.is_primary
        WHERE r.id = $1
        """,
        recipe_id,
    )
    if not row:
        return None
    liked = False
    if viewer_id:
        liked = bool(
            await pool.fetchval(
                "SELECT 1 FROM likes WHERE user_id = $1 AND recipe_id = $2",
                viewer_id,
                recipe_id,
            )
        )
    author = UserProfile(
        id=row["user_id"],
        username=row["username"],
        display_name=row["display_name"],
        avatar_url=row["avatar_url"],
        bio=row["bio"],
        recipe_count=row["recipe_count"] or 0,
        created_at=row["author_created"],
    )
    return await _recipe_from_row(dict(row), author, liked=liked)


async def list_user_recipes(user_id: UUID, viewer_id: UUID | None = None) -> list[RecipeResponse]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT r.*, ri.storage_path, ri.public_url
        FROM recipes r
        LEFT JOIN recipe_images ri ON ri.recipe_id = r.id AND ri.is_primary
        WHERE r.user_id = $1 AND r.status = 'published'
        ORDER BY r.created_at DESC
        """,
        user_id,
    )
    author = await get_profile(user_id)
    return [await _recipe_from_row(dict(r), author) for r in rows]


async def toggle_like(recipe_id: UUID, user_id: UUID) -> RecipeResponse:
    pool = await get_pool()
    exists = await pool.fetchval(
        "SELECT 1 FROM likes WHERE user_id = $1 AND recipe_id = $2",
        user_id,
        recipe_id,
    )
    if exists:
        await pool.execute("DELETE FROM likes WHERE user_id = $1 AND recipe_id = $2", user_id, recipe_id)
    else:
        await pool.execute(
            "INSERT INTO likes (user_id, recipe_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id,
            recipe_id,
        )
    recipe = await get_recipe(recipe_id, user_id)
    if not recipe:
        raise LookupError("Recipe not found")
    return recipe


async def list_comments(recipe_id: UUID) -> list[CommentResponse]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT c.*, p.username, p.display_name, p.avatar_url, p.bio, p.recipe_count, p.created_at AS author_created
        FROM comments c
        JOIN profiles p ON p.id = c.user_id
        WHERE c.recipe_id = $1
        ORDER BY c.created_at ASC
        """,
        recipe_id,
    )
    return [
        CommentResponse(
            id=r["id"],
            recipe_id=r["recipe_id"],
            user_id=r["user_id"],
            content=r["content"],
            created_at=r["created_at"],
            author=UserProfile(
                id=r["user_id"],
                username=r["username"],
                display_name=r["display_name"],
                avatar_url=r["avatar_url"],
                bio=r["bio"],
                recipe_count=r["recipe_count"] or 0,
                created_at=r["author_created"],
            ),
        )
        for r in rows
    ]


async def add_comment(recipe_id: UUID, user_id: UUID, content: str) -> CommentResponse:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO comments (recipe_id, user_id, content)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        recipe_id,
        user_id,
        content,
    )
    author = await get_profile(user_id)
    return CommentResponse(
        id=row["id"],
        recipe_id=row["recipe_id"],
        user_id=row["user_id"],
        content=row["content"],
        created_at=row["created_at"],
        author=author,
    )


async def delete_comment(comment_id: UUID, user_id: UUID) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM comments WHERE id = $1 AND user_id = $2",
        comment_id,
        user_id,
    )
    return result.endswith("1")
