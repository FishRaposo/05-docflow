"""Content fingerprinting for deduplication and change detection."""

import hashlib
from pathlib import Path


class Fingerprinter:
    """Computes SHA-256 fingerprints for document content and files.

    Used for detecting duplicate documents and determining if content has changed.
    """

    def compute_fingerprint(self, content: str) -> str:
        """Compute a SHA-256 hash of text content.

        Args:
            content: Text content to fingerprint.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def compute_file_hash(self, file_path: str) -> str:
        """Compute a SHA-256 hash of a file's binary content.

        Reads the file in chunks to handle large files efficiently.

        Args:
            file_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        sha256 = hashlib.sha256()
        path = Path(file_path)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def has_changed(self, old_fingerprint: str, new_fingerprint: str) -> bool:
        """Compare two fingerprints to determine if content has changed.

        Args:
            old_fingerprint: Previously stored fingerprint.
            new_fingerprint: Newly computed fingerprint.

        Returns:
            True if the fingerprints differ, indicating content change.
        """
        return old_fingerprint != new_fingerprint
