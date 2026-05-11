"""Document ingestion worker."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.config import settings
from docflow.db import async_session
from docflow.db.models import Chunk, Document, ProcessingJob
from docflow.parsers import get_parser
from docflow.processing.chunking import ChunkingService
from docflow.processing.deduplication import DeduplicationService
from docflow.processing.fingerprint import Fingerprinter
from docflow.processing.metadata import MetadataExtractor
from docflow.processing.versioning import VersioningService
from docflow.queue.dlq import DeadLetterQueue
from docflow.queue.redis_queue import RedisQueue
from docflow.storage.object_store import ObjectStore

logger = logging.getLogger(__name__)


class IngestWorker:
    """Worker that processes documents through the ingestion pipeline.

    Orchestrates the full pipeline: parse -> fingerprint -> dedup -> chunk -> metadata -> version.
    """

    def __init__(self) -> None:
        """Initialize the ingest worker with all processing services."""
        self.fingerprinter = Fingerprinter()
        self.deduplicator = DeduplicationService()
        self.chunker = ChunkingService()
        self.metadata_extractor = MetadataExtractor()
        self.versioner = VersioningService()
        self.object_store = ObjectStore()
        self.dlq = DeadLetterQueue()

    async def process_document(self, document_id: UUID, session: AsyncSession | None = None) -> None:
        """Process a document through the full ingestion pipeline.

        Args:
            document_id: UUID of the document to process.
            session: Optional existing database session.

        Raises:
            ValueError: If the document cannot be found or parsed.
        """
        own_session = session is None
        if own_session:
            session = async_session()

        job = ProcessingJob(
            document_id=document_id,
            stage="ingest",
            status="processing",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.commit()

        try:
            document = await self._load_document(document_id, session)
            if document is None:
                raise ValueError(f"Document {document_id} not found")

            logger.info("Processing document %s (%s)", document_id, document.title)
            await self._update_status(document_id, "processing", session)

            parser = get_parser(document.file_type)
            parsed = await parser.parse(document.file_path)

            fingerprint = self.fingerprinter.compute_fingerprint(parsed.content)
            await self._store_fingerprint(document_id, fingerprint, session)

            duplicate = await self.deduplicator.check_content_duplicate(fingerprint, session)
            if duplicate.is_duplicate:
                logger.info("Duplicate found: document %s matches %s", document_id, duplicate.existing_id)
                await self._update_status(document_id, "duplicate", session)

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()

                return

            metadata = self.metadata_extractor.extract_metadata(
                document.file_path, parsed.content
            )
            await self._store_metadata(document_id, metadata, session)

            strategy = settings.CHUNKING_STRATEGY
            if strategy == "sentence":
                chunks = self.chunker.chunk_by_sentence(parsed.content)
            elif strategy == "structure":
                chunks = self.chunker.chunk_by_structure(parsed.sections)
            elif strategy == "semantic":
                chunks = self.chunker.chunk_by_section_size(parsed.content)
            else:
                chunks = self.chunker.chunk_fixed(parsed.content)
            await self._store_chunks(document_id, chunks, session)

            await self.versioner.create_version(
                document_id,
                {"fingerprint": fingerprint, "chunks_total": len(chunks)},
                session,
            )
            await self._update_status(document_id, "ready", session)

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info("Document %s processed successfully", document_id)

        except Exception as exc:
            logger.error("Failed to process document %s: %s", document_id, exc)
            await self._update_status(document_id, "error", session)

            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

            await self.dlq.push({"document_id": str(document_id)}, str(exc))

            raise
        finally:
            if own_session and session is not None:
                await session.close()

    async def _load_document(self, document_id: UUID, session: AsyncSession) -> Any:
        """Load a document record from the database."""
        result = await session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def _update_status(self, document_id: UUID, status: str, session: AsyncSession) -> None:
        """Update the processing status of a document."""
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            await session.commit()
            logger.debug("Document %s status -> %s", document_id, status)

    async def _store_fingerprint(self, document_id: UUID, fingerprint: str, session: AsyncSession) -> None:
        """Persist the computed fingerprint for a document."""
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.content_hash = fingerprint
            doc.fingerprint = fingerprint
            await session.commit()
            logger.debug("Stored fingerprint for document %s", document_id)

    async def _store_metadata(self, document_id: UUID, metadata: Any, session: AsyncSession) -> None:
        """Persist extracted metadata for a document."""
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            existing = doc.metadata_ or {}
            existing.update({
                "language": metadata.language,
                "word_count": metadata.word_count,
                "read_time_minutes": metadata.read_time_minutes,
                "file_size_bytes": metadata.file_size_bytes,
            })
            doc.metadata_ = existing
            await session.commit()
            logger.debug("Stored metadata for document %s", document_id)

    async def _store_chunks(self, document_id: UUID, chunks: list[Any], session: AsyncSession) -> None:
        """Persist computed chunks for a document."""
        import hashlib

        for i, chunk in enumerate(chunks):
            content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
            db_chunk = Chunk(
                document_id=document_id,
                content=chunk.content,
                content_hash=content_hash,
                chunk_index=i,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata_=chunk.metadata,
            )
            session.add(db_chunk)
        await session.commit()
        logger.debug("Stored %d chunks for document %s", len(chunks), document_id)


async def run_worker() -> None:
    """Run the ingest worker in a polling loop against the Redis queue."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.info("Starting ingest worker")

    queue = RedisQueue()
    await queue.connect()
    dlq = DeadLetterQueue(queue._client)

    worker = IngestWorker()
    ingest_queue = f"{settings.QUEUE_NAME}:ingest"
    semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)

    async def _process_one(job_data: dict[str, Any]) -> None:
        doc_id = job_data.get("document_id")
        if doc_id is None:
            logger.warning("Received job without document_id: %s", job_data)
            return
        async with semaphore:
            try:
                await worker.process_document(UUID(doc_id))
            except Exception as exc:
                logger.error("Failed to process document %s: %s", doc_id, exc)
                await dlq.push(job_data, str(exc))

    try:
        while True:
            job = await queue.dequeue(ingest_queue, timeout=1)
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
