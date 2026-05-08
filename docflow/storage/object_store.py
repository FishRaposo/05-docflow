"""Object storage abstraction with local filesystem implementation."""

import logging
from pathlib import Path

from docflow.config import settings

logger = logging.getLogger(__name__)


class ObjectStore:
    """Abstract object store for file persistence.

    Provides a unified interface for saving, loading, and deleting files.
    Currently implements local filesystem storage with an S3-compatible
    interface placeholder.
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
        raise NotImplementedError(f"Storage backend not implemented: {self._backend}")

    async def delete(self, file_path: str) -> None:
        """Delete a file from storage.

        Args:
            file_path: Relative path within the storage base.
        """
        if self._backend == "local":
            self._delete_local(file_path)
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
