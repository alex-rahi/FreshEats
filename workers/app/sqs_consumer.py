"""SQS long-poll consumer for YOLO recipe moderation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from uuid import UUID

import asyncpg
import boto3

from app.config import settings
from app.pipeline.analyze import analyze_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plate-sqs-consumer")


async def _get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)


def _download_s3(bucket: str, key: str, dest: str) -> None:
    client = boto3.client("s3", region_name=settings.aws_region)
    client.download_file(bucket, key, dest)


async def _apply_result(pool: asyncpg.Pool, recipe_id: UUID, job_id: UUID | None, result) -> None:
    status = result.outcome
    decision = result.moderation_decision
    labels = sorted({d["label"] for d in result.detections})
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE recipes
                SET status = $2::recipe_status,
                    moderation_decision = $3,
                    moderation_reason = $4,
                    updated_at = NOW()
                WHERE id = $1
                """,
                recipe_id,
                status,
                decision,
                result.moderation_reason,
            )
            if job_id:
                await conn.execute(
                    """
                    UPDATE moderation_jobs
                    SET status = 'completed',
                        decision = $2,
                        detections = $3::jsonb,
                        moderation_scores = $4::jsonb,
                        current_step = 'done',
                        progress = 1,
                        completed_at = NOW()
                    WHERE id = $1
                    """,
                    job_id,
                    decision,
                    json.dumps(result.detections),
                    json.dumps(result.moderation_scores),
                )
            else:
                await conn.execute(
                    """
                    UPDATE moderation_jobs
                    SET status = 'completed',
                        decision = $2,
                        detections = $3::jsonb,
                        moderation_scores = $4::jsonb,
                        current_step = 'done',
                        progress = 1,
                        completed_at = NOW()
                    WHERE recipe_id = $1 AND status IN ('queued', 'running')
                    """,
                    recipe_id,
                    decision,
                    json.dumps(result.detections),
                    json.dumps(result.moderation_scores),
                )
            if status == "pending_review":
                priority = 10 if decision == "manual_review" else 5
                await conn.execute(
                    """
                    INSERT INTO review_queue (recipe_id, priority, detections, moderation_scores)
                    VALUES ($1, $2, $3::jsonb, $4::jsonb)
                    """,
                    recipe_id,
                    priority,
                    json.dumps(result.detections),
                    json.dumps(result.moderation_scores),
                )
    logger.info("Recipe %s → %s (%s) labels=%s", recipe_id, status, decision, labels)


async def process_message(pool: asyncpg.Pool, body: dict) -> None:
    recipe_id = UUID(body["recipe_id"])
    storage_path = body["storage_path"]
    bucket = body.get("bucket") or settings.storage_bucket_raw
    job_id = UUID(body["job_id"]) if body.get("job_id") else None

    if job_id:
        await pool.execute(
            """
            UPDATE moderation_jobs
            SET status = 'running', current_step = 'yolo_detection', started_at = NOW()
            WHERE id = $1
            """,
            job_id,
        )

    suffix = os.path.splitext(storage_path)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _download_s3(bucket, storage_path, tmp_path)
        result = analyze_path(tmp_path)
        await _apply_result(pool, recipe_id, job_id, result)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def poll_forever() -> None:
    if not settings.sqs_moderation_url:
        raise RuntimeError("SQS_MODERATION_URL is required for the SQS consumer")

    pool = await _get_pool()
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    logger.info("Polling %s", settings.sqs_moderation_url)

    # Also expose /health via a tiny side server for k8s probes
    from threading import Thread

    def _health_server():
        from fastapi import FastAPI
        import uvicorn

        app = FastAPI()

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "plate-sqs-consumer"}

        uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")

    Thread(target=_health_server, daemon=True).start()

    while True:
        resp = sqs.receive_message(
            QueueUrl=settings.sqs_moderation_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=20,
            VisibilityTimeout=300,
        )
        messages = resp.get("Messages", [])
        if not messages:
            await asyncio.sleep(0.1)
            continue
        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                await process_message(pool, body)
                sqs.delete_message(
                    QueueUrl=settings.sqs_moderation_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
            except Exception:
                logger.exception("Failed to process message %s", msg.get("MessageId"))


def main():
    asyncio.run(poll_forever())


if __name__ == "__main__":
    main()
