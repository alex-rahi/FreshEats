from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import get_current_user_id
from app.config import settings
from app.data.placeholders import PLACEHOLDER_PROFILE
from app.models.schemas import ProfileUpdate, UserProfile
from app.services import local_store, recipe_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=UserProfile)
async def get_me(user_id: UUID = Depends(get_current_user_id)):
    if settings.use_placeholders or settings.use_local_yolo:
        return local_store.get_profile(user_id) or PLACEHOLDER_PROFILE
    if settings.uses_db:
        profile = await recipe_service.get_profile(user_id)
        if not profile:
            raise HTTPException(404, "Profile not found")
        return profile
    raise HTTPException(501, "Profiles not configured")


@router.patch("/me", response_model=UserProfile)
async def update_me(body: ProfileUpdate, user_id: UUID = Depends(get_current_user_id)):
    if settings.use_placeholders or settings.use_local_yolo:
        current = local_store.get_profile(user_id) or PLACEHOLDER_PROFILE
        updated = current.model_copy(
            update={k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        )
        return local_store.upsert_profile(updated)
    if settings.uses_db:
        return await recipe_service.update_profile(user_id, **body.model_dump(exclude_unset=True))
    raise HTTPException(501, "Profiles not configured")


@router.get("/{profile_id}", response_model=UserProfile)
async def get_profile(profile_id: UUID):
    if settings.use_placeholders or settings.use_local_yolo:
        profile = local_store.get_profile(profile_id)
        if not profile:
            raise HTTPException(404, "Profile not found")
        return profile
    if settings.uses_db:
        profile = await recipe_service.get_profile(profile_id)
        if not profile:
            raise HTTPException(404, "Profile not found")
        return profile
    raise HTTPException(501, "Profiles not configured")
