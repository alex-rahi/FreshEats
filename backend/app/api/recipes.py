from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.jwt import get_current_user_id, get_optional_user_id
from app.config import settings
from app.data.placeholders import PLACEHOLDER_RECIPES
from app.models.schemas import RecipeCreate, RecipeCreateResponse, RecipeGridResponse, RecipeResponse
from app.services import local_store, recipe_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("", response_model=RecipeCreateResponse | RecipeResponse)
async def create_recipe(body: RecipeCreate, user_id: UUID = Depends(get_current_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        recipe = local_store.create_local_recipe(user_id, body.title, body.description)
        return recipe

    if settings.uses_db:
        created = await recipe_service.create_recipe(user_id, body)
        return RecipeCreateResponse(
            recipe=created["recipe"],
            upload_url=created["upload_url"],
            storage_path=created["storage_path"],
            job_id=created["job_id"],
        )
    raise HTTPException(501, "Recipe create not configured")


@router.post("/{recipe_id}/confirm-upload", response_model=RecipeResponse)
async def confirm_upload(recipe_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        raise HTTPException(400, "Use /moderation/recipes/{id}/upload for local demo")
    try:
        return await recipe_service.confirm_upload(recipe_id, user_id)
    except LookupError:
        raise HTTPException(404, "Recipe not found")
    except Exception as exc:
        raise HTTPException(502, f"Confirm upload failed: {exc}") from exc


@router.get("", response_model=RecipeGridResponse)
async def list_recipes(
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    viewer_id: UUID | None = Depends(get_optional_user_id),
):
    if settings.use_local_yolo or settings.use_placeholders:
        items = local_store.list_published(viewer_id)
        existing_ids = {r.id for r in items}
        seeded = [r for r in PLACEHOLDER_RECIPES if r.id not in existing_ids]
        return RecipeGridResponse(items=(items + seeded)[:limit], next_cursor=None)

    if settings.uses_db:
        items = await recipe_service.list_published(viewer_id, limit)
        return RecipeGridResponse(items=items, next_cursor=None)

    raise HTTPException(501, "Recipe feed not configured")


@router.get("/user/{user_id}", response_model=list[RecipeResponse])
async def user_recipes(user_id: UUID, viewer_id: UUID | None = Depends(get_optional_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        local = local_store.list_user_recipes(user_id, viewer_id)
        extras = [r for r in PLACEHOLDER_RECIPES if r.user_id == user_id]
        return local + extras
    if settings.uses_db:
        return await recipe_service.list_user_recipes(user_id, viewer_id)
    raise HTTPException(501, "User recipes not configured")


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(recipe_id: UUID, viewer_id: UUID | None = Depends(get_optional_user_id)):
    if settings.use_local_yolo or settings.use_placeholders:
        recipe = local_store.get_local_recipe(recipe_id, viewer_id)
        if recipe:
            return recipe
        for item in PLACEHOLDER_RECIPES:
            if item.id == recipe_id:
                return item
        raise HTTPException(404, "Recipe not found")
    if settings.uses_db:
        recipe = await recipe_service.get_recipe(recipe_id, viewer_id)
        if not recipe:
            raise HTTPException(404, "Recipe not found")
        return recipe
    raise HTTPException(501, "Recipe detail not configured")
