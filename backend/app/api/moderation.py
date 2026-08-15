from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.jwt import get_current_user_id
from app.config import settings
from app.models.schemas import RecipeResponse
from app.services import demo_moderation, local_storage, local_store, moderation_client

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/health")
async def moderation_health():
    """Status of the YOLO moderation engine for the upload UI."""
    base = {
        "engine": "YOLOv8",
        "policy": "food_only",
        "pipeline": ["upload", "detect", "food-only score", "publish | reject"],
        "detects": [
            "food",
            "dish",
            "produce",
            "plated meals",
        ],
        "rules": demo_moderation.RULE_CATALOG,
        "placeholder_mode": settings.use_placeholders,
        "local_yolo": settings.use_local_yolo,
    }

    if settings.use_local_yolo:
        try:
            worker = await moderation_client.worker_health()
            return {
                **base,
                "enabled": True,
                "mode": "live",
                "status": "ready" if worker.get("model_ready") or worker.get("status") == "ok" else "starting",
                "worker": worker,
            }
        except Exception as exc:
            return {
                **base,
                "enabled": True,
                "mode": "live",
                "status": "unreachable",
                "worker": {"status": "unreachable", "error": str(exc)},
            }

    if settings.use_placeholders:
        return {
            **base,
            "enabled": True,
            "mode": "demo",
            "status": "ready",
            "detail": "Food only — YOLO publishes recipe food photos; everything else is rejected.",
            "worker": None,
        }

    return {**base, "enabled": False, "mode": "off", "status": "disabled", "worker": None}


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

    # Placeholder demo without live YOLO: heuristic detections + real rule outcomes
    if settings.use_placeholders and not settings.use_local_yolo:
        if not local_storage.upload_exists(storage_path):
            raise HTTPException(400, "Upload image before running moderation")
        from pathlib import Path

        from app.config import settings as cfg

        path = Path(cfg.uploads_dir) / storage_path
        result = demo_moderation.analyze_image_file(path)
        return local_store.apply_moderation_result(recipe_id, result)

    if not settings.use_local_yolo:
        raise HTTPException(404, "Local YOLO pipeline disabled")

    if not local_storage.upload_exists(storage_path):
        raise HTTPException(400, "Upload image before running moderation")

    try:
        result = await moderation_client.analyze_storage_path(storage_path)
    except Exception as exc:
        raise HTTPException(502, f"YOLO worker failed: {exc}") from exc

    # Always persist outcome (including rejects) so the UI can show rule results.
    saved = local_store.apply_moderation_result(recipe_id, result)
    if result.get("status") == "rejected":
        return saved
    return saved
