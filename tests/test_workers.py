"""Tests for the DocFlow worker processes."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from docflow.workers.embed_worker import EmbedWorker
from docflow.workers.ingest_worker import IngestWorker


def _make_doc_session(mock_doc=None):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_doc)
    mock_result.scalars = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    return mock_session


class TestIngestWorker:
    """Tests for the document ingestion worker."""

    @pytest.mark.asyncio
    async def test_duplicate_check_skips_processing(self) -> None:
        worker = IngestWorker()

        doc_id = uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.title = "Test Document"
        mock_doc.file_type = "md"
        mock_doc.file_path = "/tmp/test.md"
        mock_doc.status = "pending"

        mock_session = _make_doc_session(mock_doc)

        mock_parsed = MagicMock()
        mock_parsed.content = "test content"
        mock_parsed.sections = []

        duplicate_match = MagicMock()
        duplicate_match.is_duplicate = True
        duplicate_match.existing_id = uuid4()

        worker.fingerprinter.compute_fingerprint = MagicMock(return_value="abc123")
        worker.deduplicator.check_content_duplicate = AsyncMock(return_value=duplicate_match)
        worker.dlq.push = AsyncMock()

        with patch.object(worker, "_store_fingerprint", AsyncMock()):
            with patch.object(worker, "_update_status", AsyncMock()):
                with patch("docflow.workers.ingest_worker.get_parser") as mock_get_parser:
                    mock_parser = MagicMock()
                    mock_parser.parse = AsyncMock(return_value=mock_parsed)
                    mock_get_parser.return_value = mock_parser

                    await worker.process_document(doc_id, mock_session)

                    mock_session.add.assert_called()
                    worker.deduplicator.check_content_duplicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_worker_creates_processing_job(self) -> None:
        worker = IngestWorker()

        doc_id = uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.title = "Test"
        mock_doc.file_type = "md"
        mock_doc.file_path = "/tmp/test.md"

        mock_session = _make_doc_session(mock_doc)

        mock_parsed = MagicMock()
        mock_parsed.content = "content"
        mock_parsed.sections = []

        duplicate_match = MagicMock()
        duplicate_match.is_duplicate = False

        worker.fingerprinter.compute_fingerprint = MagicMock(return_value="fp123")
        worker.deduplicator.check_content_duplicate = AsyncMock(return_value=duplicate_match)
        worker.deduplicator.register_fingerprint = MagicMock()
        worker.metadata_extractor.extract_metadata = MagicMock(
            return_value=MagicMock(
                language="en", word_count=100, read_time_minutes=1, file_size_bytes=1024
            )
        )
        worker.chunker.chunk_fixed = MagicMock(return_value=[])
        worker.versioner.create_version = AsyncMock()
        worker.dlq.push = AsyncMock()

        with patch.object(worker, "_store_fingerprint", AsyncMock()):
            with patch.object(worker, "_store_metadata", AsyncMock()):
                with patch.object(worker, "_store_chunks", AsyncMock()):
                    with patch.object(worker, "_update_status", AsyncMock()):
                        with patch(
                            "docflow.workers.ingest_worker.get_parser"
                        ) as mock_get_parser:
                            mock_parser = MagicMock()
                            mock_parser.parse = AsyncMock(return_value=mock_parsed)
                            mock_get_parser.return_value = mock_parser

                            await worker.process_document(doc_id, mock_session)

                            mock_session.add.assert_called()
                            assert mock_session.commit.call_count >= 1


class TestEmbedWorker:
    """Tests for the embedding worker."""

    def _make_session(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_result.scalars = MagicMock()
        mock_result.scalars.return_value.all = MagicMock(
            return_value=MagicMock()
        )
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        return mock_session

    @pytest.mark.asyncio
    async def test_embed_worker_stores_vectors(self) -> None:
        worker = EmbedWorker()

        doc_id = uuid4()
        chunk_id = uuid4()

        mock_chunk = MagicMock()
        mock_chunk.id = chunk_id
        mock_chunk.content = "sample chunk text"
        mock_chunk.chunk_index = 0

        mock_session = self._make_session()

        mock_embeddings = [[0.1, 0.2, 0.3]]
        worker.embedding_service.batch_embed = AsyncMock(return_value=mock_embeddings)
        worker.dlq.push = AsyncMock()

        with patch.object(worker, "_load_chunks", AsyncMock(return_value=[mock_chunk])):
            with patch.object(worker, "_store_vectors", AsyncMock()):
                await worker.process_chunks(doc_id, mock_session)

                worker.embedding_service.batch_embed.assert_called_once_with(
                    ["sample chunk text"]
                )
                worker._store_vectors.assert_called_once_with(
                    [chunk_id], mock_embeddings, mock_session
                )

    @pytest.mark.asyncio
    async def test_embed_worker_creates_processing_job(self) -> None:
        worker = EmbedWorker()

        doc_id = uuid4()
        chunk_id = uuid4()

        mock_chunk = MagicMock()
        mock_chunk.id = chunk_id
        mock_chunk.content = "text"
        mock_chunk.chunk_index = 0

        mock_session = self._make_session()

        worker.embedding_service.batch_embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        worker.dlq.push = AsyncMock()

        with patch.object(worker, "_load_chunks", AsyncMock(return_value=[mock_chunk])):
            with patch.object(worker, "_store_vectors", AsyncMock()):
                await worker.process_chunks(doc_id, mock_session)

                mock_session.add.assert_called()
                assert mock_session.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_embed_worker_dlq_push_on_failure(self) -> None:
        worker = EmbedWorker()

        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock())
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        worker.dlq.push = AsyncMock()

        with patch.object(worker, "_load_chunks", AsyncMock(return_value=[])):
            with pytest.raises(ValueError, match="No chunks found"):
                await worker.process_chunks(doc_id, mock_session)

            worker.dlq.push.assert_called_once()


class TestWorkerDLQIntegration:
    """Tests for DLQ push behavior during worker failures."""

    @pytest.mark.asyncio
    async def test_ingest_worker_failure_records_error(self) -> None:
        worker = IngestWorker()
        doc_id = uuid4()

        mock_session = _make_doc_session(None)
        worker.dlq.push = AsyncMock()

        with pytest.raises(ValueError, match="not found"):
            await worker.process_document(doc_id, mock_session)

        mock_session.add.assert_called()
        assert mock_session.commit.call_count >= 1
        worker.dlq.push.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_worker_failure_records_error(self) -> None:
        worker = EmbedWorker()
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock())
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        worker.dlq.push = AsyncMock()

        with patch.object(
            worker, "_load_chunks", AsyncMock(side_effect=RuntimeError("DB connection lost"))
        ):
            with pytest.raises(RuntimeError, match="DB connection lost"):
                await worker.process_chunks(doc_id, mock_session)

        mock_session.add.assert_called()
        assert mock_session.commit.call_count >= 2
        worker.dlq.push.assert_called_once()
