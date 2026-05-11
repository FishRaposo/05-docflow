"""Vector store operations for embedding storage and similarity search."""

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.db.models import Chunk

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

    Uses pgvector through SQLAlchemy for persistent vector storage
    and cosine distance similarity search.
    """

    async def add_vectors(
        self,
        chunk_ids: list[UUID],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Add embedding vectors to existing chunk records in the database.

        Args:
            chunk_ids: UUIDs of the corresponding chunks.
            embeddings: Embedding vectors to store.
            metadata: Optional metadata for each vector.
            session: Database session.
        """
        for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
            result = await session.execute(
                select(Chunk).where(Chunk.id == chunk_id)
            )
            chunk = result.scalar_one_or_none()
            if chunk:
                chunk.embedding = embedding
                if metadata and i < len(metadata):
                    chunk.metadata_ = metadata[i]
        await session.commit()
        logger.debug("Added %d vectors to store", len(chunk_ids))

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> list[SearchResult]:
        """Find the most similar vectors to a query embedding.

        Uses pgvector's cosine distance operator (<=>) for efficient
        nearest-neighbor search.

        Args:
            query_embedding: Query vector to search against.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters.
            session: Database session.

        Returns:
            List of SearchResult objects sorted by similarity score.
        """
        vector_str = f"[{','.join(str(v) for v in query_embedding)}]"

        stmt = select(
            Chunk.id,
            Chunk.document_id,
            Chunk.content,
            Chunk.embedding.cosine_distance(query_embedding).label("distance"),
            Chunk.metadata_,
        ).where(
            Chunk.embedding.isnot(None)
        ).order_by(
            Chunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k)

        if filters and "document_id" in filters:
            stmt = stmt.where(Chunk.document_id == filters["document_id"])

        result = await session.execute(stmt)
        rows = result.all()

        results: list[SearchResult] = []
        for row in rows:
            score = 1.0 - float(row.distance) if row.distance is not None else 0.0
            results.append(
                SearchResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content or "",
                    score=max(0.0, min(1.0, score)),
                    metadata=row.metadata_ or {},
                )
            )

        return results

    async def delete_vectors(
        self, chunk_ids: list[UUID], session: AsyncSession | None = None
    ) -> None:
        """Remove embedding vectors from the store.

        Args:
            chunk_ids: UUIDs of chunks to remove.
            session: Database session.
        """
        for chunk_id in chunk_ids:
            result = await session.execute(
                select(Chunk).where(Chunk.id == chunk_id)
            )
            chunk = result.scalar_one_or_none()
            if chunk:
                chunk.embedding = None
        await session.commit()
        logger.debug("Deleted %d vectors from store", len(chunk_ids))
