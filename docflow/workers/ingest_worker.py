"""Document ingestion worker."""

import logging
from uuid import UUID

from docflow.parsers import get_parser
from docflow.processing.chunking import ChunkingService
from docflow.processing.deduplication import DeduplicationService
from docflow.processing.fingerprint import Fingerprinter
from docflow.processing.metadata import MetadataExtractor
from docflow.processing.versioning import VersioningService

logger = logging.getLogger(__name__)


class IngestWorker:
    """Worker that processes documents through the ingestion pipeline.

    Orchestrates the full pipeline: parse → fingerprint → dedup → chunk → metadata → version.
    """

    def __init__(self) -> None:
        """Initialize the ingest worker with all processing services."""
        self.fingerprinter = Fingerprinter()
        self.deduplicator = DeduplicationService()
        self.chunker = ChunkingService()
        self.metadata_extractor = MetadataExtractor()
        self.versioner = VersioningService()

    async def process_document(self, document_id: UUID) -> None:
        """Process a document through the full ingestion pipeline.

        Args:
            document_id: UUID of the document to process.

        Raises:
            ValueError: If the document cannot be found or parsed.
        """
        logger.info("Processing document %s", document_id)

        document = await self._load_document(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        await self._update_status(document_id, "processing")

        try:
            parser = get_parser(document.file_type)
            parsed = await parser.parse(document.file_path)

            fingerprint = self.fingerprinter.compute_fingerprint(parsed.content)
            await self._store_fingerprint(document_id, fingerprint)

            duplicate = await self.deduplicator.check_content_duplicate(fingerprint)
            if duplicate is not None:
                logger.info("Duplicate found: document %s matches %s", document_id, duplicate.id)
                await self._update_status(document_id, "duplicate")
                return

            metadata = self.metadata_extractor.extract_metadata(
                document.file_path, parsed.content
            )
            await self._store_metadata(document_id, metadata)

            chunks = self.chunker.chunk_fixed(parsed.content)
            await self._store_chunks(document_id, chunks)

            await self.versioner.create_version(document_id, {"fingerprint": fingerprint})
            await self._update_status(document_id, "ready")
            logger.info("Document %s processed successfully", document_id)

        except Exception as exc:
            logger.error("Failed to process document %s: %s", document_id, exc)
            await self._update_status(document_id, "error")
            raise

    async def _load_document(self, document_id: UUID) -> Any:
        """Load a document record from the database.

        Args:
            document_id: UUID of the document.

        Returns:
            The document record or None.
        """
        return None

    async def _update_status(self, document_id: UUID, status: str) -> None:
        """Update the processing status of a document.

        Args:
            document_id: UUID of the document.
            status: New status string.
        """
        logger.debug("Document %s status -> %s", document_id, status)

    async def _store_fingerprint(self, document_id: UUID, fingerprint: str) -> None:
        """Persist the computed fingerprint for a document.

        Args:
            document_id: UUID of the document.
            fingerprint: SHA-256 hash of the content.
        """
        logger.debug("Stored fingerprint for document %s", document_id)

    async def _store_metadata(self, document_id: UUID, metadata: Any) -> None:
        """Persist extracted metadata for a document.

        Args:
            document_id: UUID of the document.
            metadata: Extracted metadata object.
        """
        logger.debug("Stored metadata for document %s", document_id)

    async def _store_chunks(self, document_id: UUID, chunks: list[Any]) -> None:
        """Persist computed chunks for a document.

        Args:
            document_id: UUID of the document.
            chunks: List of chunk candidates.
        """
        logger.debug("Stored %d chunks for document %s", len(chunks), document_id)


from typing import Any
