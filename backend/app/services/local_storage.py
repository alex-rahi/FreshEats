"""Persist uploaded recipe images for local YOLO analysis."""

from __future__ import annotations

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


def sniff_image_ext(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return ".jpg"


def align_storage_path(storage_path: str, data: bytes) -> str:
    """Keep filename stem, fix extension so StaticFiles content-type matches bytes."""
    ext = sniff_image_ext(data)
    stem = Path(storage_path).with_suffix("").as_posix()
    return f"{stem}{ext}"


async def save_upload_file(recipe_id: UUID, storage_path: str, file: UploadFile) -> str:
    data = await file.read()
    aligned = align_storage_path(storage_path, data)
    dest = _uploads_root() / aligned
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return aligned


def public_file_url(storage_path: str) -> str:
    """Local demo URL served by backend static mount."""
    return f"/media/{storage_path}"
