"""HTTP API for synchronous YOLO moderation of recipe images."""

import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.pipeline.analyze import analyze_bytes, analyze_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plate-worker-http")

app = FastAPI(title="Plate YOLO Worker", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    model_exists = os.path.isfile(settings.yolo_model_path)
    return {
        "status": "ok",
        "service": "plate-yolo-worker",
        "model_path": settings.yolo_model_path,
        "model_ready": model_exists,
    }


@app.post("/analyze")
async def analyze_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")

    try:
        result = analyze_bytes(data, suffix)
    except Exception as exc:
        logger.exception("Analyze failed")
        raise HTTPException(500, f"Analysis failed: {exc}") from exc

    labels = sorted({d["label"] for d in result.detections})
    return {
        "status": result.outcome,
        "moderation_decision": result.moderation_decision,
        "moderation_reason": result.moderation_reason,
        "detections": result.detections,
        "detection_labels": labels,
        "moderation_scores": result.moderation_scores,
        "rules": result.rules,
    }


@app.post("/analyze-path")
async def analyze_local_path(storage_path: str):
    full_path = os.path.join(settings.uploads_dir, storage_path)
    if not os.path.isfile(full_path):
        raise HTTPException(404, f"File not found: {storage_path}")

    try:
        result = analyze_path(full_path)
    except Exception as exc:
        logger.exception("Analyze path failed")
        raise HTTPException(500, f"Analysis failed: {exc}") from exc

    labels = sorted({d["label"] for d in result.detections})
    return {
        "status": result.outcome,
        "moderation_decision": result.moderation_decision,
        "moderation_reason": result.moderation_reason,
        "detections": result.detections,
        "detection_labels": labels,
        "moderation_scores": result.moderation_scores,
        "rules": result.rules,
    }
