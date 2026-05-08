"""Document versioning service for tracking content changes."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentVersion(BaseModel):
    """A snapshot of a document at a point in time."""

    id: UUID = Field(default_factory=uuid4, description="Version UUID")
    document_id: UUID = Field(description="Parent document UUID")
    version: int = Field(description="Monotonically increasing version number")
    fingerprint: str = Field(default="", description="Content fingerprint at this version")
    change_type: str = Field(default="created", description="Type of change")
    change_summary: str = Field(default="", description="Human-readable change description")
    chunks_added: int = Field(default=0, description="New chunks in this version")
    chunks_removed: int = Field(default=0, description="Removed chunks from previous")
    created_at: datetime = Field(default_factory=datetime.now, description="Version timestamp")


class VersionDiff(BaseModel):
    """Comparison result between two document versions."""

    version_a: int = Field(description="First version number")
    version_b: int = Field(description="Second version number")
    fingerprint_changed: bool = Field(description="Whether fingerprints differ")
    chunks_added: int = Field(default=0, description="Chunks in B not in A")
    chunks_removed: int = Field(default=0, description="Chunks in A not in B")
    chunks_unchanged: int = Field(default=0, description="Chunks common to both")
    summary: str = Field(default="", description="Human-readable diff summary")


class VersioningService:
    """Service for managing document versions and change tracking.

    Creates version snapshots when content changes and supports
    version comparison for auditing.
    """

    def __init__(self) -> None:
        """Initialize the versioning service with an in-memory version store."""
        self._versions: dict[UUID, list[DocumentVersion]] = {}

    def create_version(
        self,
        document_id: UUID,
        changes: dict[str, Any],
    ) -> DocumentVersion:
        """Create a new version for a document.

        Args:
            document_id: UUID of the document.
            changes: Dictionary with change details (fingerprint, chunks info).

        Returns:
            The newly created DocumentVersion.
        """
        history = self._versions.get(document_id, [])
        version_number = len(history) + 1
        change_type = "created" if version_number == 1 else "updated"

        version = DocumentVersion(
            document_id=document_id,
            version=version_number,
            fingerprint=changes.get("fingerprint", ""),
            change_type=change_type,
            chunks_added=changes.get("chunks_added", 0),
            chunks_removed=changes.get("chunks_removed", 0),
        )

        if document_id not in self._versions:
            self._versions[document_id] = []
        self._versions[document_id].append(version)

        return version

    def get_version_history(self, document_id: UUID) -> list[DocumentVersion]:
        """Retrieve the full version history for a document.

        Args:
            document_id: UUID of the document.

        Returns:
            List of DocumentVersion objects in chronological order.
        """
        return self._versions.get(document_id, [])

    def compare_versions(self, document_id: UUID, v1: int, v2: int) -> VersionDiff:
        """Compare two versions of a document.

        Args:
            document_id: UUID of the document.
            v1: First version number.
            v2: Second version number.

        Returns:
            VersionDiff describing the differences between versions.
        """
        history = self._versions.get(document_id, [])

        version_a = next((v for v in history if v.version == v1), None)
        version_b = next((v for v in history if v.version == v2), None)

        if version_a is None or version_b is None:
            raise ValueError(f"Version(s) not found: v1={v1}, v2={v2}")

        fingerprint_changed = version_a.fingerprint != version_b.fingerprint

        chunks_added = max(0, version_b.chunks_added - version_a.chunks_added)
        chunks_removed = max(0, version_a.chunks_added - version_b.chunks_added)

        summary = f"Version {v1} -> {v2}"
        if fingerprint_changed:
            summary += ": content changed"
        else:
            summary += ": no content change"

        return VersionDiff(
            version_a=v1,
            version_b=v2,
            fingerprint_changed=fingerprint_changed,
            chunks_added=chunks_added,
            chunks_removed=chunks_removed,
            summary=summary,
        )
