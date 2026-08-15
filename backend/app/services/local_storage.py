"""Persist uploaded recipe images for local YOLO analysis."""

from __future__ import annotations

import io
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from PIL import Image

from app.config import settings

_MAX_EDGE = 2048
_JPEG_QUALITY = 92


def _uploads_root() -> Path:
    root = Path(settings.uploads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_exists(storage_path: str) -> bool:
    return (_uploads_root() / storage_path).is_file()


def _normalize_to_jpeg(data: bytes) -> bytes:
    """Center-crop to sample landscape (~485×297), then encode a sharp JPEG."""
    target_aspect = 485 / 297
    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        w, h = rgb.size
        src_aspect = w / h
        if src_aspect > target_aspect:
            crop_w = max(1, round(h * target_aspect))
            left = (w - crop_w) // 2
            rgb = rgb.crop((left, 0, left + crop_w, h))
        elif src_aspect < target_aspect:
            crop_h = max(1, round(w / target_aspect))
            top = (h - crop_h) // 2
            rgb = rgb.crop((0, top, w, top + crop_h))

        w, h = rgb.size
        longest = max(w, h)
        if longest > _MAX_EDGE:
            scale = _MAX_EDGE / longest
            rgb = rgb.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))),
                Image.Resampling.LANCZOS,
            )
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return out.getvalue()


def align_storage_path(storage_path: str, data: bytes | None = None) -> str:
    """Local demo stores normalized JPEGs — keep a .jpg key for StaticFiles."""
    stem = Path(storage_path).with_suffix("").as_posix()
    return f"{stem}.jpg"


async def save_upload_file(recipe_id: UUID, storage_path: str, file: UploadFile) -> str:
    raw = await file.read()
    try:
        data = _normalize_to_jpeg(raw)
    except Exception:
        data = raw
    aligned = align_storage_path(storage_path, data)
    dest = _uploads_root() / aligned
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return aligned


def public_file_url(storage_path: str) -> str:
    """Local demo URL served by backend static mount."""
    return f"/media/{storage_path}"
