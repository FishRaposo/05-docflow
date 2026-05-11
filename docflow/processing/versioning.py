"""Document versioning service for tracking content changes."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.db.models import Document


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
    chunks_total: int = Field(default=0, description="Total chunks at this version")
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
    version comparison for auditing. Stores version history in the
    Document.metadata_ JSON field for persistence across restarts.
    """

    async def create_version(
        self,
        document_id: UUID,
        changes: dict[str, Any],
        session: AsyncSession,
    ) -> DocumentVersion:
        """Create a new version for a document.

        Args:
            document_id: UUID of the document.
            changes: Dictionary with change details (fingerprint, chunks info).
            session: Database session.

        Returns:
            The newly created DocumentVersion.
        """
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        metadata = doc.metadata_ or {}
        versions: list[dict[str, Any]] = metadata.get("versions", [])

        version_number = len(versions) + 1
        change_type = "created" if version_number == 1 else "updated"

        version = DocumentVersion(
            document_id=document_id,
            version=version_number,
            fingerprint=changes.get("fingerprint", ""),
            change_type=change_type,
            chunks_added=changes.get("chunks_added", 0),
            chunks_removed=changes.get("chunks_removed", 0),
            chunks_total=changes.get("chunks_total", 0),
        )

        versions.append(version.model_dump(mode="json"))
        metadata["versions"] = versions
        doc.metadata_ = metadata
        doc.version = version_number
        await session.commit()

        return version

    async def get_version_history(
        self, document_id: UUID, session: AsyncSession
    ) -> list[DocumentVersion]:
        """Retrieve the full version history for a document.

        Args:
            document_id: UUID of the document.
            session: Database session.

        Returns:
            List of DocumentVersion objects in chronological order.
        """
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None or doc.metadata_ is None:
            return []

        versions_data = doc.metadata_.get("versions", [])
        return [DocumentVersion(**v) for v in versions_data]

    async def compare_versions(
        self, document_id: UUID, v1: int, v2: int, session: AsyncSession
    ) -> VersionDiff:
        """Compare two versions of a document.

        Args:
            document_id: UUID of the document.
            v1: First version number.
            v2: Second version number.
            session: Database session.

        Returns:
            VersionDiff describing the differences between versions.
        """
        history = await self.get_version_history(document_id, session)

        version_a = next((v for v in history if v.version == v1), None)
        version_b = next((v for v in history if v.version == v2), None)

        if version_a is None or version_b is None:
            raise ValueError(f"Version(s) not found: v1={v1}, v2={v2}")

        fingerprint_changed = version_a.fingerprint != version_b.fingerprint

        delta = version_b.chunks_total - version_a.chunks_total
        chunks_added = max(0, delta)
        chunks_removed = max(0, -delta)
        chunks_unchanged = min(version_a.chunks_total, version_b.chunks_total)

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
            chunks_unchanged=chunks_unchanged,
            summary=summary,
        )
