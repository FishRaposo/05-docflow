"""Object storage abstraction with local filesystem and S3 implementations."""

import asyncio
import logging
from pathlib import Path

from docflow.config import settings

logger = logging.getLogger(__name__)


class ObjectStore:
    """Abstract object store for file persistence.

    Provides a unified interface for saving, loading, and deleting files.
    Supports local filesystem storage and S3-compatible backends.
    """

    def __init__(self, backend: str | None = None, base_path: str | None = None) -> None:
        """Initialize the object store.

        Args:
            backend: Storage backend type ('local' or 's3').
            base_path: Base directory for local storage.
        """
        self._backend = backend or settings.STORAGE_BACKEND
        self._base_path = Path(base_path or settings.STORAGE_PATH)

    async def save(self, file_path: str, content: bytes) -> str:
        """Save file content to storage.

        Args:
            file_path: Relative path within the storage base.
            content: File content as bytes.

        Returns:
            Full path to the saved file.
        """
        if self._backend == "local":
            return self._save_local(file_path, content)
        if self._backend == "s3":
            return await self._save_s3(file_path, content)
        raise NotImplementedError(f"Storage backend not implemented: {self._backend}")

    async def load(self, file_path: str) -> bytes:
        """Load file content from storage.

        Args:
            file_path: Relative path within the storage base.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if self._backend == "local":
            return self._load_local(file_path)
        if self._backend == "s3":
            return await self._load_s3(file_path)
        raise NotImplementedError(f"Storage backend not implemented: {self._backend}")

    async def delete(self, file_path: str) -> None:
        """Delete a file from storage.

        Args:
            file_path: Relative path within the storage base.
        """
        if self._backend == "local":
            self._delete_local(file_path)
        elif self._backend == "s3":
            await self._delete_s3(file_path)
        else:
            raise NotImplementedError(f"Storage backend not implemented: {self._backend}")

    async def exists(self, file_path: str) -> bool:
        """Check if a file exists in storage.

        Args:
            file_path: Relative path within the storage base.

        Returns:
            True if the file exists.
        """
        if self._backend == "local":
            full_path = self._base_path / file_path
            return full_path.exists()
        if self._backend == "s3":
            return await self._exists_s3(file_path)
        raise NotImplementedError(f"Storage backend not implemented: {self._backend}")

    def _save_local(self, file_path: str, content: bytes) -> str:
        """Save content to the local filesystem.

        Args:
            file_path: Relative path within the base directory.
            content: File content as bytes.

        Returns:
            Full path to the saved file.
        """
        full_path = self._base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        logger.debug("Saved file to %s", full_path)
        return str(full_path)

    def _load_local(self, file_path: str) -> bytes:
        """Load content from the local filesystem.

        Args:
            file_path: Relative path within the base directory.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        full_path = self._base_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        return full_path.read_bytes()

    def _delete_local(self, file_path: str) -> None:
        """Delete a file from the local filesystem.

        Args:
            file_path: Relative path within the base directory.
        """
        full_path = self._base_path / file_path
        if full_path.exists():
            full_path.unlink()
            logger.debug("Deleted file: %s", full_path)

    async def _save_s3(self, file_path: str, content: bytes) -> str:
        """Save content to S3-compatible storage via boto3.

        Args:
            file_path: S3 object key.
            content: File content as bytes.

        Returns:
            S3 URI of the saved object.
        """
        import boto3

        s3 = boto3.client("s3")
        bucket = self._bucket_from_path()
        await asyncio.to_thread(s3.put_object, Bucket=bucket, Key=file_path, Body=content)
        logger.debug("Saved s3://%s/%s", bucket, file_path)
        return f"s3://{bucket}/{file_path}"

    async def _load_s3(self, file_path: str) -> bytes:
        """Load content from S3-compatible storage via boto3.

        Args:
            file_path: S3 object key.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client("s3")
        bucket = self._bucket_from_path()
        try:
            response = await asyncio.to_thread(
                s3.get_object, Bucket=bucket, Key=file_path
            )
            return response["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"S3 object not found: s3://{bucket}/{file_path}") from exc
            raise

    async def _delete_s3(self, file_path: str) -> None:
        """Delete an object from S3-compatible storage.

        Args:
            file_path: S3 object key.
        """
        import boto3

        s3 = boto3.client("s3")
        bucket = self._bucket_from_path()
        await asyncio.to_thread(s3.delete_object, Bucket=bucket, Key=file_path)
        logger.debug("Deleted s3://%s/%s", bucket, file_path)

    async def _exists_s3(self, file_path: str) -> bool:
        """Check if an object exists in S3 storage.

        Args:
            file_path: S3 object key.

        Returns:
            True if the object exists.
        """
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client("s3")
        bucket = self._bucket_from_path()
        try:
            await asyncio.to_thread(s3.head_object, Bucket=bucket, Key=file_path)
            return True
        except ClientError:
            return False

    def _bucket_from_path(self) -> str:
        """Extract the S3 bucket name from the configured storage path.

        Returns:
            Bucket name string.
        """
        return str(self._base_path).replace("s3://", "").split("/")[0]
