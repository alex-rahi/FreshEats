from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import get_current_user_id
from app.config import settings
from app.data.placeholders import PLACEHOLDER_COMMENTS, PLACEHOLDER_RECIPES
from app.models.schemas import CommentCreate, CommentResponse, RecipeResponse
from app.services import local_store, recipe_service

router = APIRouter(tags=["social"])


def _materialize_placeholder(recipe_id: UUID):
    match = next((r for r in PLACEHOLDER_RECIPES if r.id == recipe_id), None)
    if not match:
        return False
    created = local_store.create_local_recipe(match.user_id, match.title, match.description)
    store = local_store._local_recipes  # noqa: SLF001
    data = store.pop(created.id)
    data["id"] = recipe_id
    data["status"] = "published"
    data["image_url"] = match.image_url
    data["like_count"] = match.like_count
    data["comment_count"] = match.comment_count
    store[recipe_id] = data
    local_store._local_likes[recipe_id] = set()  # noqa: SLF001
    local_store._local_comments[recipe_id] = []  # noqa: SLF001
    return True


@router.post("/recipes/{recipe_id}/like", response_model=RecipeResponse)
async def like_recipe(recipe_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        recipe = local_store.get_local_recipe(recipe_id)
        if not recipe and not _materialize_placeholder(recipe_id):
            raise HTTPException(404, "Recipe not found")
        return local_store.toggle_like(recipe_id, user_id)
    if settings.uses_db:
        try:
            return await recipe_service.toggle_like(recipe_id, user_id)
        except LookupError:
            raise HTTPException(404, "Recipe not found")
    raise HTTPException(501, "Likes not configured")


@router.delete("/recipes/{recipe_id}/like", response_model=RecipeResponse)
async def unlike_recipe(recipe_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    return await like_recipe(recipe_id, user_id)


@router.get("/recipes/{recipe_id}/comments", response_model=list[CommentResponse])
async def get_comments(recipe_id: UUID):
    if settings.use_local_yolo or settings.use_placeholders:
        local = local_store.list_comments(recipe_id)
        if local:
            return local
        return [CommentResponse(**c) for c in PLACEHOLDER_COMMENTS.get(str(recipe_id), [])]
    if settings.uses_db:
        return await recipe_service.list_comments(recipe_id)
    raise HTTPException(501, "Comments not configured")


@router.post("/recipes/{recipe_id}/comments", response_model=CommentResponse)
async def create_comment(
    recipe_id: UUID,
    body: CommentCreate,
    user_id: UUID = Depends(get_current_user_id),
):
    if settings.use_local_yolo or settings.use_placeholders:
        if not local_store.get_local_recipe(recipe_id) and not _materialize_placeholder(recipe_id):
            raise HTTPException(404, "Recipe not found")
        return local_store.add_comment(recipe_id, user_id, body.content)
    if settings.uses_db:
        return await recipe_service.add_comment(recipe_id, user_id, body.content)
    raise HTTPException(501, "Comments not configured")


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(comment_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        if not local_store.delete_comment(comment_id, user_id):
            raise HTTPException(404, "Comment not found")
        return None
    if settings.uses_db:
        if not await recipe_service.delete_comment(comment_id, user_id):
            raise HTTPException(404, "Comment not found")
        return None
    raise HTTPException(501, "Comments not configured")
