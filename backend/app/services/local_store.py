"""In-memory recipe store for local YOLO pipeline and demo uploads."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.data.placeholders import PLACEHOLDER_AUTHORS, PLACEHOLDER_PROFILE, PLACEHOLDER_USER_ID
from app.models.schemas import CommentResponse, RecipeImage, RecipeResponse, RecipeStatus, UserProfile

_local_recipes: dict[UUID, dict] = {}
_local_comments: dict[UUID, list[dict]] = {}
_local_likes: dict[UUID, set[UUID]] = {}
_local_review_queue: dict[UUID, dict] = {}
_local_profiles: dict[UUID, UserProfile] = {
    PLACEHOLDER_USER_ID: PLACEHOLDER_PROFILE,
}


def _author(user_id: UUID) -> UserProfile:
    if user_id in _local_profiles:
        return _local_profiles[user_id]
    data = PLACEHOLDER_AUTHORS.get(user_id, {"username": "cook", "display_name": "Cook"})
    return UserProfile(id=user_id, username=data["username"], display_name=data["display_name"])


def upsert_profile(profile: UserProfile) -> UserProfile:
    _local_profiles[profile.id] = profile
    return profile


def get_profile(user_id: UUID) -> UserProfile | None:
    return _local_profiles.get(user_id) or (
        PLACEHOLDER_PROFILE if user_id == PLACEHOLDER_USER_ID else None
    )


def create_local_recipe(user_id: UUID, title: str, description: str | None) -> RecipeResponse:
    recipe_id = uuid4()
    storage_path = f"{user_id}/{recipe_id}.jpg"
    recipe = {
        "id": recipe_id,
        "user_id": user_id,
        "title": title,
        "description": description,
        "status": RecipeStatus.UPLOADING.value,
        "moderation_decision": None,
        "moderation_reason": None,
        "like_count": 0,
        "comment_count": 0,
        "image_url": None,
        "images": [
            RecipeImage(storage_path=storage_path, public_url=None, is_primary=True),
        ],
        "detection_labels": [],
        "created_at": datetime.now(timezone.utc),
        "storage_path": storage_path,
    }
    _local_recipes[recipe_id] = recipe
    _local_comments[recipe_id] = []
    _local_likes[recipe_id] = set()
    return _to_response(recipe, user_id)


def _to_response(recipe: dict, viewer_id: UUID | None = None) -> RecipeResponse:
    liked = False
    if viewer_id is not None:
        liked = viewer_id in _local_likes.get(recipe["id"], set())
    return RecipeResponse(
        id=recipe["id"],
        user_id=recipe["user_id"],
        title=recipe["title"],
        description=recipe.get("description"),
        status=recipe["status"],
        moderation_decision=recipe.get("moderation_decision"),
        moderation_reason=recipe.get("moderation_reason"),
        like_count=recipe.get("like_count", 0),
        comment_count=recipe.get("comment_count", 0),
        liked_by_me=liked,
        image_url=recipe.get("image_url"),
        images=recipe.get("images", []),
        detection_labels=recipe.get("detection_labels", []),
        author=_author(recipe["user_id"]),
        created_at=recipe.get("created_at"),
    )


def get_local_recipe(recipe_id: UUID, viewer_id: UUID | None = None) -> RecipeResponse | None:
    recipe = _local_recipes.get(recipe_id)
    if not recipe:
        return None
    return _to_response(recipe, viewer_id)


def mark_processing(recipe_id: UUID) -> RecipeResponse:
    recipe = _local_recipes[recipe_id]
    recipe["status"] = RecipeStatus.PROCESSING.value
    return _to_response(recipe)


def set_image_url(recipe_id: UUID, url: str) -> None:
    recipe = _local_recipes[recipe_id]
    recipe["image_url"] = url
    images = recipe.get("images") or []
    if images:
        images[0].public_url = url


def apply_moderation_result(recipe_id: UUID, result: dict) -> RecipeResponse:
    recipe = _local_recipes[recipe_id]
    recipe["status"] = result.get("status", RecipeStatus.PUBLISHED.value)
    recipe["moderation_decision"] = result.get("moderation_decision", "publish")
    recipe["moderation_reason"] = result.get("moderation_reason")
    recipe["detection_labels"] = result.get("detection_labels", [])

    if recipe["status"] == RecipeStatus.PENDING_REVIEW.value:
        review_id = uuid4()
        priority = 10 if result.get("moderation_decision") == "manual_review" else 5
        _local_review_queue[review_id] = {
            "id": review_id,
            "recipe_id": recipe_id,
            "priority": priority,
            "review_status": "pending",
            "created_at": datetime.now(timezone.utc),
            "detections": result.get("detections", []),
            "moderation_scores": result.get("moderation_scores", []),
        }
    elif recipe["status"] == RecipeStatus.PUBLISHED.value:
        profile = get_profile(recipe["user_id"])
        if profile:
            upsert_profile(profile.model_copy(update={"recipe_count": profile.recipe_count + 1}))

    return _to_response(recipe)


def list_published(viewer_id: UUID | None = None) -> list[RecipeResponse]:
    items = [
        _to_response(r, viewer_id)
        for r in sorted(_local_recipes.values(), key=lambda x: x["created_at"], reverse=True)
        if r["status"] == RecipeStatus.PUBLISHED.value
    ]
    return items


def list_user_recipes(user_id: UUID, viewer_id: UUID | None = None) -> list[RecipeResponse]:
    return [
        _to_response(r, viewer_id)
        for r in sorted(_local_recipes.values(), key=lambda x: x["created_at"], reverse=True)
        if r["user_id"] == user_id and r["status"] == RecipeStatus.PUBLISHED.value
    ]


def toggle_like(recipe_id: UUID, user_id: UUID) -> RecipeResponse:
    recipe = _local_recipes[recipe_id]
    likes = _local_likes.setdefault(recipe_id, set())
    if user_id in likes:
        likes.remove(user_id)
        recipe["like_count"] = max(recipe["like_count"] - 1, 0)
    else:
        likes.add(user_id)
        recipe["like_count"] += 1
    return _to_response(recipe, user_id)


def add_comment(recipe_id: UUID, user_id: UUID, content: str) -> CommentResponse:
    comment = {
        "id": uuid4(),
        "recipe_id": recipe_id,
        "user_id": user_id,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    _local_comments.setdefault(recipe_id, []).append(comment)
    _local_recipes[recipe_id]["comment_count"] += 1
    return CommentResponse(**comment, author=_author(user_id))


def list_comments(recipe_id: UUID) -> list[CommentResponse]:
    return [
        CommentResponse(**c, author=_author(c["user_id"]))
        for c in _local_comments.get(recipe_id, [])
    ]


def delete_comment(comment_id: UUID, user_id: UUID) -> bool:
    for recipe_id, comments in _local_comments.items():
        for idx, comment in enumerate(comments):
            if comment["id"] == comment_id and comment["user_id"] == user_id:
                comments.pop(idx)
                if recipe_id in _local_recipes:
                    _local_recipes[recipe_id]["comment_count"] = max(
                        _local_recipes[recipe_id]["comment_count"] - 1, 0
                    )
                return True
    return False


def list_review_queue(limit: int = 50) -> list[dict]:
    items = sorted(
        _local_review_queue.values(),
        key=lambda item: (-item["priority"], item["created_at"]),
    )
    return [i for i in items if i["review_status"] == "pending"][:limit]


def submit_review(review_id: UUID, outcome: str, notes: str | None = None) -> bool:
    item = _local_review_queue.get(review_id)
    if not item or item["review_status"] != "pending":
        return False
    recipe = _local_recipes.get(item["recipe_id"])
    if not recipe:
        return False
    status_map = {
        "publish": RecipeStatus.PUBLISHED.value,
        "approve": RecipeStatus.PUBLISHED.value,
        "reject": RecipeStatus.REJECTED.value,
    }
    recipe["status"] = status_map.get(outcome, RecipeStatus.PENDING_REVIEW.value)
    recipe["moderation_decision"] = outcome
    recipe["moderation_reason"] = notes
    item["review_status"] = "completed"
    item["reviewer_notes"] = notes
    if recipe["status"] == RecipeStatus.PUBLISHED.value:
        profile = get_profile(recipe["user_id"])
        if profile:
            upsert_profile(profile.model_copy(update={"recipe_count": profile.recipe_count + 1}))
    return True


def admin_stats() -> dict:
    published = sum(1 for r in _local_recipes.values() if r["status"] == "published")
    rejected = sum(1 for r in _local_recipes.values() if r["status"] == "rejected")
    pending = len(list_review_queue())
    return {
        "pending_reviews": pending,
        "published_today": published,
        "rejected_today": rejected,
        "total_recipes": len(_local_recipes),
        "total_users": len(_local_profiles),
    }
