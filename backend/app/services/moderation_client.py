"""HTTP client for the YOLO moderation worker."""

from __future__ import annotations

import httpx

from app.config import settings


async def worker_health() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(f"{settings.worker_url.rstrip('/')}/health")
        res.raise_for_status()
        return res.json()


async def analyze_storage_path(storage_path: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"{settings.worker_url.rstrip('/')}/analyze-path",
            params={"storage_path": storage_path},
        )
        res.raise_for_status()
        return res.json()
