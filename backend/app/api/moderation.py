from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.jwt import get_current_user_id
from app.config import settings
from app.models.schemas import RecipeResponse
from app.services import local_storage, local_store, moderation_client

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/health")
async def moderation_health():
    if not settings.use_local_yolo:
        return {"enabled": False}
    try:
        worker = await moderation_client.worker_health()
        return {"enabled": True, "worker": worker}
    except Exception as exc:
        return {"enabled": True, "worker": {"status": "unreachable", "error": str(exc)}}


@router.post("/recipes/{recipe_id}/upload", response_model=RecipeResponse)
async def upload_for_moderation(
    recipe_id: UUID,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
):
    if not settings.use_local_yolo and not settings.use_placeholders:
        raise HTTPException(404, "Local upload pipeline disabled")

    recipe = local_store.get_local_recipe(recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise HTTPException(404, "Recipe not found")

    storage_path = recipe.images[0].storage_path if recipe.images else f"{user_id}/{recipe_id}.jpg"
    storage_path = await local_storage.save_upload_file(recipe_id, storage_path, file)
    url = local_storage.public_file_url(storage_path)
    local_store.set_image_url(recipe_id, url, storage_path=storage_path)
    return local_store.mark_processing(recipe_id)


@router.post("/recipes/{recipe_id}/run", response_model=RecipeResponse)
async def run_local_moderation(recipe_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    recipe = local_store.get_local_recipe(recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise HTTPException(404, "Recipe not found")

    storage_path = recipe.images[0].storage_path if recipe.images else ""

    # Placeholder demo without YOLO: auto-publish
    if settings.use_placeholders and not settings.use_local_yolo:
        result = {
            "status": "published",
            "moderation_decision": "publish",
            "detection_labels": ["food"],
            "detections": [],
            "moderation_scores": [],
            "rules": [],
            "moderation_reason": "Demo mode auto-publish",
        }
        return local_store.apply_moderation_result(recipe_id, result)

    if not settings.use_local_yolo:
        raise HTTPException(404, "Local YOLO pipeline disabled")

    if not local_storage.upload_exists(storage_path):
        raise HTTPException(400, "Upload image before running moderation")

    try:
        result = await moderation_client.analyze_storage_path(storage_path)
    except Exception as exc:
        raise HTTPException(502, f"YOLO worker failed: {exc}") from exc

    if result.get("status") == "rejected":
        local_store.apply_moderation_result(recipe_id, result)
        raise HTTPException(422, detail={
            "message": "Image rejected by moderation",
            "reason": result.get("moderation_decision"),
            "labels": result.get("detection_labels", []),
        })

    return local_store.apply_moderation_result(recipe_id, result)
