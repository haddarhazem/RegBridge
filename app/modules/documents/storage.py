import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3

from app.core.config import Settings, get_settings
from app.core.observability import dependency_result, elapsed_ms
import time


class ObjectStorage(Protocol):
    async def put_file(self, path: Path, key: str, content_type: str) -> None: ...
    def stream(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...


class S3ObjectStorage:
    """Private S3-compatible storage adapter; document logic never calls boto3 directly."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
            use_ssl=settings.object_storage_secure,
        )

    async def put_file(self, path: Path, key: str, content_type: str) -> None:
        started = time.perf_counter()
        extra_args: dict[str, str] = {"ContentType": content_type}
        if self.settings.object_storage_server_side_encryption:
            extra_args["ServerSideEncryption"] = self.settings.object_storage_server_side_encryption
        try:
            await asyncio.to_thread(self.client.upload_file, str(path), self.settings.object_storage_bucket, key, ExtraArgs=extra_args)
        except Exception:
            dependency_result(dependency="object_storage", operation="write", status="error", duration_ms=elapsed_ms(started), error_category="STORAGE_ERROR")
            raise
        dependency_result(dependency="object_storage", operation="write", status="ok", duration_ms=elapsed_ms(started))

    async def _read_chunk(self, body, size: int) -> bytes:
        return await asyncio.to_thread(body.read, size)

    async def _stream(self, key: str) -> AsyncIterator[bytes]:
        started = time.perf_counter()
        try:
            response = await asyncio.to_thread(self.client.get_object, Bucket=self.settings.object_storage_bucket, Key=key)
        except Exception:
            dependency_result(dependency="object_storage", operation="read", status="error", duration_ms=elapsed_ms(started), error_category="STORAGE_ERROR")
            raise
        body = response["Body"]
        try:
            while chunk := await self._read_chunk(body, 1024 * 1024):
                yield chunk
        finally:
            await asyncio.to_thread(body.close)
            dependency_result(dependency="object_storage", operation="read", status="ok", duration_ms=elapsed_ms(started))

    def stream(self, key: str) -> AsyncIterator[bytes]:
        return self._stream(key)

    async def delete(self, key: str) -> None:
        started = time.perf_counter()
        try:
            await asyncio.to_thread(self.client.delete_object, Bucket=self.settings.object_storage_bucket, Key=key)
        except Exception:
            dependency_result(dependency="object_storage", operation="delete", status="error", duration_ms=elapsed_ms(started), error_category="STORAGE_ERROR")
            raise
        dependency_result(dependency="object_storage", operation="delete", status="ok", duration_ms=elapsed_ms(started))


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    return S3ObjectStorage(get_settings())
