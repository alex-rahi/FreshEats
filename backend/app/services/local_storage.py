"""Persist uploaded recipe images for local YOLO analysis."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.config import settings


def _uploads_root() -> Path:
    root = Path(settings.uploads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_exists(storage_path: str) -> bool:
    return (_uploads_root() / storage_path).is_file()


async def save_upload_file(recipe_id: UUID, storage_path: str, file: UploadFile) -> str:
    dest = _uploads_root() / storage_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    dest.write_bytes(data)
    return str(dest)


def public_file_url(storage_path: str) -> str:
    """Local demo URL served by backend static mount."""
    return f"/media/{storage_path}"
