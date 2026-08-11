"""S3 presigned uploads + CloudFront public URLs."""

from __future__ import annotations

import boto3
from botocore.client import Config

from app.config import settings


def _client():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        config=Config(signature_version="s3v4"),
    )


def presign_put(bucket: str, key: str, content_type: str = "image/jpeg", expires: int = 900) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def public_url(key: str) -> str:
    if settings.cloudfront_domain:
        domain = settings.cloudfront_domain.rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/{key}"
    return f"https://{settings.storage_bucket_recipes}.s3.{settings.aws_region}.amazonaws.com/{key}"


def download_to_path(bucket: str, key: str, dest: str) -> str:
    _client().download_file(bucket, key, dest)
    return dest


def copy_object(src_bucket: str, src_key: str, dest_bucket: str, dest_key: str) -> None:
    _client().copy_object(
        CopySource={"Bucket": src_bucket, "Key": src_key},
        Bucket=dest_bucket,
        Key=dest_key,
    )
