"""MinIO client (S3-compatible) — eval reports, model weights, chunk snapshots.

Uses boto3 in async-friendly wrappers (asyncio.to_thread) so calls don't block
the event loop. Credentials come from Vault via vault.get_minio_access_key/secret_key.

Usage:
    from app.infra.minio import get_minio
    client = get_minio()
    await client.upload_json("eval-reports", "rag_report.json", data)
"""

import asyncio
import io
import json
from typing import Any

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.infra.vault import get_minio_access_key, get_minio_secret_key

logger = structlog.get_logger()

_client: "MinIOClient | None" = None


class MinIOClient:
    def __init__(self) -> None:
        settings = get_settings()
        scheme = "https" if settings.minio_secure else "http"
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{settings.minio_endpoint}",
            aws_access_key_id=get_minio_access_key(),
            aws_secret_access_key=get_minio_secret_key(),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",  # required by boto3 even for MinIO
        )
        self._settings = settings

    async def ping(self) -> bool:
        try:
            await asyncio.to_thread(self._s3.list_buckets)
            return True
        except Exception as exc:
            logger.warning("minio_ping_failed", error=str(exc))
            return False

    async def ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it does not exist."""
        def _create():
            try:
                self._s3.head_bucket(Bucket=bucket)
            except ClientError:
                self._s3.create_bucket(Bucket=bucket)

        await asyncio.to_thread(_create)

    async def upload_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        await self.ensure_bucket(bucket)
        await asyncio.to_thread(
            self._s3.upload_fileobj,
            io.BytesIO(data),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("minio_upload", bucket=bucket, key=key, size=len(data))

    async def upload_json(self, bucket: str, key: str, data: Any) -> None:
        payload = json.dumps(data, indent=2).encode()
        await self.upload_bytes(bucket, key, payload, content_type="application/json")

    async def download_bytes(self, bucket: str, key: str) -> bytes:
        buf = io.BytesIO()
        await asyncio.to_thread(self._s3.download_fileobj, bucket, key, buf)
        return buf.getvalue()

    async def download_json(self, bucket: str, key: str) -> Any:
        raw = await self.download_bytes(bucket, key)
        return json.loads(raw)

    async def object_exists(self, bucket: str, key: str) -> bool:
        try:
            await asyncio.to_thread(self._s3.head_object, Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    async def presign_get(self, bucket: str, key: str, expires: int = 3600) -> str:
        return await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )


def init_minio() -> MinIOClient:
    global _client
    _client = MinIOClient()
    logger.info("minio_client_created")
    return _client


def get_minio() -> MinIOClient:
    if _client is None:
        raise RuntimeError("MinIO not initialised — call init_minio() in lifespan first.")
    return _client
