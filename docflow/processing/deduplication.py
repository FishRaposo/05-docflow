"""Document and chunk deduplication service."""

import hashlib
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DuplicateMatch(BaseModel):
    """Result of a duplicate check operation."""

    is_duplicate: bool = False
    existing_id: UUID | None = None
    similarity: float = 0.0


class DeduplicationService:
    """Service for detecting and handling duplicate documents and chunks.

    Uses content fingerprinting for exact matches and similarity scoring
    for near-duplicate detection.
    """

    def __init__(self) -> None:
        """Initialize the deduplication service with an empty fingerprint store."""
        self._fingerprints: dict[str, UUID] = {}
        self._chunk_hashes: dict[str, UUID] = {}

    def check_content_duplicate(self, fingerprint: str) -> DuplicateMatch:
        """Check if a document fingerprint matches an existing document.

        Args:
            fingerprint: SHA-256 fingerprint of the document content.

        Returns:
            DuplicateMatch indicating whether a duplicate was found.
        """
        if fingerprint in self._fingerprints:
            return DuplicateMatch(
                is_duplicate=True,
                existing_id=self._fingerprints[fingerprint],
                similarity=1.0,
            )
        return DuplicateMatch(is_duplicate=False)

    def check_chunk_duplicate(self, content_hash: str) -> DuplicateMatch:
        """Check if a chunk content hash matches an existing chunk.

        Args:
            content_hash: Hash of the chunk content.

        Returns:
            DuplicateMatch indicating whether a duplicate chunk was found.
        """
        if content_hash in self._chunk_hashes:
            return DuplicateMatch(
                is_duplicate=True,
                existing_id=self._chunk_hashes[content_hash],
                similarity=1.0,
            )
        return DuplicateMatch(is_duplicate=False)

    def register_fingerprint(self, fingerprint: str, document_id: UUID) -> None:
        """Register a document fingerprint in the deduplication store.

        Args:
            fingerprint: SHA-256 fingerprint to register.
            document_id: UUID of the document.
        """
        self._fingerprints[fingerprint] = document_id

    def register_chunk_hash(self, content_hash: str, chunk_id: UUID) -> None:
        """Register a chunk content hash in the deduplication store.

        Args:
            content_hash: Hash of the chunk content.
            chunk_id: UUID of the chunk.
        """
        self._chunk_hashes[content_hash] = chunk_id

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
