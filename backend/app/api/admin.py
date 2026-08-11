from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.db.pool import get_pool
from app.models.schemas import AdminStats, ReviewDecision, ReviewQueueItem, RecipeResponse
from app.services import local_store, recipe_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_admin_secret: str | None):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(401, "Invalid admin secret")


@router.get("/stats", response_model=AdminStats)
async def stats(x_admin_secret: str | None = Header(default=None)):
    _require_admin(x_admin_secret)
    if settings.use_placeholders or settings.use_local_yolo:
        return AdminStats(**local_store.admin_stats())
    if settings.uses_db:
        pool = await get_pool()
        pending = await pool.fetchval(
            "SELECT COUNT(*) FROM review_queue WHERE review_status = 'pending'"
        )
        published = await pool.fetchval("SELECT COUNT(*) FROM recipes WHERE status = 'published'")
        rejected = await pool.fetchval("SELECT COUNT(*) FROM recipes WHERE status = 'rejected'")
        total = await pool.fetchval("SELECT COUNT(*) FROM recipes")
        users = await pool.fetchval("SELECT COUNT(*) FROM profiles")
        return AdminStats(
            pending_reviews=pending or 0,
            published_today=published or 0,
            rejected_today=rejected or 0,
            total_recipes=total or 0,
            total_users=users or 0,
        )
    return AdminStats()


@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def review_queue(x_admin_secret: str | None = Header(default=None)):
    _require_admin(x_admin_secret)
    if settings.use_placeholders or settings.use_local_yolo:
        items = local_store.list_review_queue()
        result: list[ReviewQueueItem] = []
        for item in items:
            recipe = local_store.get_local_recipe(item["recipe_id"])
            result.append(
                ReviewQueueItem(
                    id=item["id"],
                    recipe_id=item["recipe_id"],
                    priority=item["priority"],
                    review_status=item["review_status"],
                    recipe=recipe,
                    detections=item.get("detections", []),
                    moderation_scores=item.get("moderation_scores", []),
                    created_at=item.get("created_at"),
                )
            )
        return result

    if settings.uses_db:
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT * FROM review_queue
            WHERE review_status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 50
            """
        )
        result = []
        for row in rows:
            recipe = await recipe_service.get_recipe(row["recipe_id"])
            detections = row["detections"] or []
            scores = row["moderation_scores"] or []
            if isinstance(detections, str):
                import json
                detections = json.loads(detections)
            if isinstance(scores, str):
                import json
                scores = json.loads(scores)
            result.append(
                ReviewQueueItem(
                    id=row["id"],
                    recipe_id=row["recipe_id"],
                    priority=row["priority"],
                    review_status=row["review_status"],
                    recipe=recipe,
                    detections=detections,
                    moderation_scores=scores,
                    created_at=row["created_at"],
                )
            )
        return result
    return []


@router.post("/review/{review_id}", response_model=RecipeResponse)
async def submit_review(
    review_id: UUID,
    body: ReviewDecision,
    x_admin_secret: str | None = Header(default=None),
):
    _require_admin(x_admin_secret)
    if settings.use_placeholders or settings.use_local_yolo:
        ok = local_store.submit_review(review_id, body.outcome, body.notes)
        if not ok:
            raise HTTPException(404, "Review item not found")
        for item in local_store._local_review_queue.values():  # noqa: SLF001
            if item["id"] == review_id:
                recipe = local_store.get_local_recipe(item["recipe_id"])
                if recipe:
                    return recipe
        raise HTTPException(404, "Recipe not found")

    if settings.uses_db:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM review_queue WHERE id = $1", review_id)
        if not row or row["review_status"] != "pending":
            raise HTTPException(404, "Review item not found")
        status_map = {
            "publish": "published",
            "approve": "published",
            "reject": "rejected",
        }
        new_status = status_map.get(body.outcome, "pending_review")
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE recipes
                    SET status = $2::recipe_status,
                        moderation_decision = $3,
                        moderation_reason = $4,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["recipe_id"],
                    new_status,
                    body.outcome,
                    body.notes,
                )
                await conn.execute(
                    """
                    UPDATE review_queue
                    SET review_status = 'completed', reviewer_notes = $2, reviewed_at = NOW()
                    WHERE id = $1
                    """,
                    review_id,
                    body.notes,
                )
        recipe = await recipe_service.get_recipe(row["recipe_id"])
        if not recipe:
            raise HTTPException(404, "Recipe not found")
        return recipe

    raise HTTPException(501, "Admin review not configured")
