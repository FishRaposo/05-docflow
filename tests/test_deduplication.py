"""Tests for deduplication and fingerprinting."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from docflow.processing.deduplication import DeduplicationService
from docflow.processing.fingerprint import Fingerprinter


class TestFingerprinter:
    """Tests for the content fingerprinter."""

    def test_compute_fingerprint_deterministic(self, fingerprinter: Fingerprinter) -> None:
        """Test that the same content produces the same fingerprint."""
        content = "Hello, World!"
        fp1 = fingerprinter.compute_fingerprint(content)
        fp2 = fingerprinter.compute_fingerprint(content)
        assert fp1 == fp2

    def test_compute_fingerprint_different_content(self, fingerprinter: Fingerprinter) -> None:
        """Test that different content produces different fingerprints."""
        fp1 = fingerprinter.compute_fingerprint("Content A")
        fp2 = fingerprinter.compute_fingerprint("Content B")
        assert fp1 != fp2

    def test_compute_fingerprint_normalizes_case(self, fingerprinter: Fingerprinter) -> None:
        """Test that fingerprints are case-insensitive."""
        fp1 = fingerprinter.compute_fingerprint("Hello World")
        fp2 = fingerprinter.compute_fingerprint("hello world")
        assert fp1 == fp2

    def test_compute_fingerprint_normalizes_whitespace(self, fingerprinter: Fingerprinter) -> None:
        """Test that leading/trailing whitespace is normalized."""
        fp1 = fingerprinter.compute_fingerprint("Hello World")
        fp2 = fingerprinter.compute_fingerprint("  Hello World  ")
        assert fp1 == fp2

    def test_has_changed_true(self, fingerprinter: Fingerprinter) -> None:
        """Test that different fingerprints indicate a change."""
        assert fingerprinter.has_changed("abc", "def") is True

    def test_has_changed_false(self, fingerprinter: Fingerprinter) -> None:
        """Test that identical fingerprints indicate no change."""
        assert fingerprinter.has_changed("abc", "abc") is False

    def test_compute_file_hash(self, fingerprinter: Fingerprinter, tmp_path: "Path") -> None:
        """Test file hash computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        h1 = fingerprinter.compute_file_hash(str(test_file))
        h2 = fingerprinter.compute_file_hash(str(test_file))
        assert h1 == h2
        assert len(h1) == 64


class TestDeduplicationService:
    """Tests for the deduplication service."""

    @pytest.mark.asyncio
    async def test_detect_duplicate_content(self, deduplication_service: DeduplicationService) -> None:
        """Test detection of duplicate content fingerprints."""
        doc_id = uuid4()
        fingerprint = "abc123"

        mock_doc = MagicMock()
        mock_doc.fingerprint = None
        mock_doc.content_hash = None

        stored_ids: list = [None]

        async def mock_commit():
            pass

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        mock_dup_result = MagicMock()
        mock_dup_result.scalar_one_or_none.return_value = doc_id

        session = AsyncMock()
        session.commit = mock_commit

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_result_inner = MagicMock()
                mock_result_inner.scalar_one_or_none.return_value = mock_doc
                return mock_result_inner
            return mock_dup_result

        session.execute = mock_execute

        await deduplication_service.register_fingerprint(fingerprint, doc_id, session)
        assert mock_doc.fingerprint == fingerprint

        session2 = AsyncMock()
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = doc_id
        session2.execute.return_value = dup_result
        session2.commit = AsyncMock()

        result = await deduplication_service.check_content_duplicate(fingerprint, session2)
        assert result.is_duplicate is True
        assert result.existing_id == doc_id

    @pytest.mark.asyncio
    async def test_no_duplicate(self, deduplication_service: DeduplicationService) -> None:
        """Test that new content is not flagged as duplicate."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await deduplication_service.check_content_duplicate("nonexistent", session)
        assert result.is_duplicate is False

    def test_merge_chunks(self, deduplication_service: DeduplicationService) -> None:
        """Test that duplicate chunks are merged."""
        chunks = [
            {"id": "1", "content": "Same content"},
            {"id": "2", "content": "Same content"},
            {"id": "3", "content": "Different content"},
        ]
        merged = deduplication_service.merge_duplicate_chunks(chunks)
        assert len(merged) == 2

    def test_fingerprint_comparison(self) -> None:
        """Test similarity computation between texts."""
        similarity = DeduplicationService.compute_similarity(
            "the cat sat on the mat",
            "the cat sat on the mat",
        )
        assert similarity == 1.0

    def test_fingerprint_comparison_different(self) -> None:
        """Test similarity between completely different texts."""
        similarity = DeduplicationService.compute_similarity(
            "alpha beta gamma",
            "delta epsilon zeta",
        )
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_chunk_duplicate_detection(self, deduplication_service: DeduplicationService) -> None:
        """Test chunk-level duplicate detection."""
        chunk_id = uuid4()
        content_hash = "chunk_hash_123"

        mock_chunk = MagicMock()
        mock_chunk.content_hash = None

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chunk
        session.execute.return_value = mock_result
        session.commit = AsyncMock()

        await deduplication_service.register_chunk_hash(content_hash, chunk_id, session)
        assert mock_chunk.content_hash == content_hash
