"""Embedding worker for processing chunk embedding jobs."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.config import settings
from docflow.db import async_session
from docflow.db.models import Chunk, Document, ProcessingJob
from docflow.processing.embedding import EmbeddingService
from docflow.queue.dlq import DeadLetterQueue
from docflow.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)


class EmbedWorker:
    """Worker that generates embeddings for document chunks.

    Batches chunks for efficient embedding and stores vectors in the vector store.
    """

    def __init__(self) -> None:
        """Initialize the embed worker with an embedding service."""
        self.embedding_service = EmbeddingService()
        self.dlq = DeadLetterQueue()

    async def process_chunks(self, document_id: UUID, session: AsyncSession | None = None) -> None:
        """Generate embeddings for all chunks of a document.

        Args:
            document_id: UUID of the document whose chunks to embed.
            session: Optional existing database session.

        Raises:
            ValueError: If no chunks are found for the document.
        """
        own_session = session is None
        if own_session:
            session = async_session()

        job = ProcessingJob(
            document_id=document_id,
            stage="embed",
            status="processing",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.commit()

        try:
            logger.info("Embedding chunks for document %s", document_id)

            chunks = await self._load_chunks(document_id, session)
            if not chunks:
                raise ValueError(f"No chunks found for document {document_id}")

            texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.batch_embed(texts)

            chunk_ids = [chunk.id for chunk in chunks]
            await self._store_vectors(chunk_ids, embeddings, session)

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info("Embedded %d chunks for document %s", len(chunks), document_id)

        except Exception as exc:
            logger.error("Failed to embed chunks for document %s: %s", document_id, exc)

            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "error"
                await session.commit()

            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

            await self.dlq.push({"document_id": str(document_id)}, str(exc))

            raise
        finally:
            if own_session and session is not None:
                await session.close()

    async def _load_chunks(self, document_id: UUID, session: AsyncSession) -> list[Any]:
        """Load chunks from the database for a document."""
        result = await session.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())

    async def _store_vectors(
        self, chunk_ids: list[UUID], embeddings: list[list[float]], session: AsyncSession
    ) -> None:
        """Store computed embeddings in the vector store."""
        params = [
            {"id": chunk_id, "embedding": embedding}
            for chunk_id, embedding in zip(chunk_ids, embeddings)
        ]
        stmt = (
            update(Chunk)
            .where(Chunk.id == bindparam("id"))
            .values(embedding=bindparam("embedding"))
        )
        await session.execute(stmt, params)
        await session.commit()
        logger.debug("Stored %d vectors", len(embeddings))


async def run_worker() -> None:
    """Run the embed worker in a polling loop against the Redis queue."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.info("Starting embed worker")

    queue = RedisQueue()
    await queue.connect()
    dlq = DeadLetterQueue(queue._client)

    worker = EmbedWorker()
    embed_queue = f"{settings.QUEUE_NAME}:embed"
    semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)

    async def _process_one(job_data: dict[str, Any]) -> None:
        doc_id = job_data.get("document_id")
        if doc_id is None:
            logger.warning("Received job without document_id: %s", job_data)
            return
        async with semaphore:
            try:
                await worker.process_chunks(UUID(doc_id))
            except Exception as exc:
                logger.error("Failed to embed document %s: %s", doc_id, exc)
                await dlq.push(job_data, str(exc))

    try:
        while True:
            job = await queue.dequeue(embed_queue, timeout=1)
            if job:
                doc_id = job.get("document_id")
                if doc_id is None:
                    logger.warning("Received job without document_id: %s", job)
                    continue
                asyncio.create_task(_process_one(job))
            await asyncio.sleep(1)
    finally:
        await queue.disconnect()


if __name__ == "__main__":
    asyncio.run(run_worker())
