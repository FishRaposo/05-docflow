"""Document and chunk deduplication service."""

import hashlib
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.db.models import Chunk, Document


class DuplicateMatch(BaseModel):
    """Result of a duplicate check operation."""

    is_duplicate: bool = False
    existing_id: UUID | None = None
    similarity: float = 0.0


class DeduplicationService:
    """Service for detecting and handling duplicate documents and chunks.

    Uses content fingerprinting for exact matches and similarity scoring
    for near-duplicate detection. Queries the database for persistence
    across restarts.
    """

    async def check_content_duplicate(
        self, fingerprint: str, session: AsyncSession
    ) -> DuplicateMatch:
        """Check if a document fingerprint matches an existing document.

        Args:
            fingerprint: SHA-256 fingerprint of the document content.
            session: Database session.

        Returns:
            DuplicateMatch indicating whether a duplicate was found.
        """
        result = await session.execute(
            select(Document.id).where(Document.fingerprint == fingerprint)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None:
            return DuplicateMatch(
                is_duplicate=True,
                existing_id=existing_id,
                similarity=1.0,
            )
        return DuplicateMatch(is_duplicate=False)

    async def check_chunk_duplicate(
        self, content_hash: str, session: AsyncSession
    ) -> DuplicateMatch:
        """Check if a chunk content hash matches an existing chunk.

        Args:
            content_hash: Hash of the chunk content.
            session: Database session.

        Returns:
            DuplicateMatch indicating whether a duplicate chunk was found.
        """
        result = await session.execute(
            select(Chunk.id).where(Chunk.content_hash == content_hash)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None:
            return DuplicateMatch(
                is_duplicate=True,
                existing_id=existing_id,
                similarity=1.0,
            )
        return DuplicateMatch(is_duplicate=False)

    async def register_fingerprint(
        self, fingerprint: str, document_id: UUID, session: AsyncSession
    ) -> None:
        """Register a document fingerprint in the database.

        Args:
            fingerprint: SHA-256 fingerprint to register.
            document_id: UUID of the document.
            session: Database session.
        """
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.fingerprint = fingerprint
            doc.content_hash = fingerprint
            await session.commit()

    async def register_chunk_hash(
        self, content_hash: str, chunk_id: UUID, session: AsyncSession
    ) -> None:
        """Register a chunk content hash in the database.

        Args:
            content_hash: Hash of the chunk content.
            chunk_id: UUID of the chunk.
            session: Database session.
        """
        result = await session.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        chunk = result.scalar_one_or_none()
        if chunk:
            chunk.content_hash = content_hash
            await session.commit()

    def merge_duplicate_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge duplicate chunks by keeping the most recent version.

        Args:
            chunks: List of chunk dictionaries with 'content' and 'id' fields.

        Returns:
            Deduplicated list of chunks.
        """
        seen: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            content = chunk.get("content", "")
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if content_hash not in seen:
                seen[content_hash] = chunk

        return list(seen.values())

    @staticmethod
    def compute_similarity(text_a: str, text_b: str) -> float:
        """Compute a simple Jaccard similarity between two texts.

        Uses word-level tokenization for a quick similarity estimate.

        Args:
            text_a: First text to compare.
            text_b: Second text to compare.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a and not words_b:
            return 1.0
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
