"""SQS helpers for moderation jobs."""

from __future__ import annotations

import json

import boto3

from app.config import settings


def _client():
    return boto3.client("sqs", region_name=settings.aws_region)


def enqueue_moderation(recipe_id: str, storage_path: str, job_id: str | None = None) -> str:
    if not settings.sqs_moderation_url:
        raise RuntimeError("SQS_MODERATION_URL not configured")
    body = {
        "recipe_id": recipe_id,
        "storage_path": storage_path,
        "job_id": job_id,
        "bucket": settings.storage_bucket_raw,
    }
    resp = _client().send_message(
        QueueUrl=settings.sqs_moderation_url,
        MessageBody=json.dumps(body),
    )
    return resp["MessageId"]
