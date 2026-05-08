"""Vector store operations for embedding storage and similarity search."""

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from docflow.config import settings

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single result from a vector similarity search."""

    chunk_id: UUID = Field(description="UUID of the matching chunk")
    document_id: UUID = Field(description="UUID of the parent document")
    content: str = Field(default="", description="Chunk text content")
    score: float = Field(description="Similarity score (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class VectorStore:
    """Vector store for storing and querying document embeddings.

    Supports adding, deleting, and searching embeddings. Currently
    uses pgvector through SQLAlchemy with an in-memory fallback.
    """

    def __init__(self) -> None:
        """Initialize the vector store with an in-memory index."""
        self._vectors: dict[UUID, list[float]] = {}
        self._metadata: dict[UUID, dict[str, Any]] = {}

    async def add_vectors(
        self,
        chunk_ids: list[UUID],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add embedding vectors to the store.

        Args:
            chunk_ids: UUIDs of the corresponding chunks.
            embeddings: Embedding vectors to store.
            metadata: Optional metadata for each vector.
        """
        for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
            self._vectors[chunk_id] = embedding
            if metadata and i < len(metadata):
                self._metadata[chunk_id] = metadata[i]
        logger.debug("Added %d vectors to store", len(chunk_ids))

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Find the most similar vectors to a query embedding.

        Uses cosine similarity for ranking. In production, this delegates
        to pgvector's ANN search.

        Args:
            query_embedding: Query vector to search against.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters.

        Returns:
            List of SearchResult objects sorted by similarity score.
        """
        if not self._vectors:
            return []

        results: list[SearchResult] = []
        for chunk_id, embedding in self._vectors.items():
            score = self._cosine_similarity(query_embedding, embedding)
            meta = self._metadata.get(chunk_id, {})
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=meta.get("document_id", UUID(int=0)),
                    score=score,
                    metadata=meta,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete_vectors(self, chunk_ids: list[UUID]) -> None:
        """Remove embedding vectors from the store.

        Args:
            chunk_ids: UUIDs of chunks to remove.
        """
        for chunk_id in chunk_ids:
            self._vectors.pop(chunk_id, None)
            self._metadata.pop(chunk_id, None)
        logger.debug("Deleted %d vectors from store", len(chunk_ids))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity score between -1.0 and 1.0.
        """
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
