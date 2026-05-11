"""Tests for document versioning service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from docflow.processing.versioning import VersioningService, VersionDiff


class TestVersioningService:
    """Tests for the versioning service."""

    def _make_doc_mock(self, metadata: dict | None = None, version: int = 1):
        """Create a mock Document for versioning tests."""
        doc = MagicMock()
        doc.metadata_ = metadata
        doc.version = version
        return doc

    def _make_session(self, doc_mock):
        """Create a mock AsyncSession that returns the given document."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc_mock
        session.execute.return_value = mock_result
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_create_version(self, versioning_service: VersioningService) -> None:
        """Test creating a first version for a document."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        version = await versioning_service.create_version(doc_id, {"fingerprint": "abc123"}, session)

        assert version.document_id == doc_id
        assert version.version == 1
        assert version.fingerprint == "abc123"
        assert version.change_type == "created"
        assert "versions" in doc.metadata_

    @pytest.mark.asyncio
    async def test_version_history(self, versioning_service: VersioningService) -> None:
        """Test retrieving the full version history."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        await versioning_service.create_version(doc_id, {"fingerprint": "fp1"}, session)
        await versioning_service.create_version(doc_id, {"fingerprint": "fp2"}, session)
        await versioning_service.create_version(doc_id, {"fingerprint": "fp3"}, session)

        history = await versioning_service.get_version_history(doc_id, session)
        assert len(history) == 3
        assert [v.version for v in history] == [1, 2, 3]
        assert [v.fingerprint for v in history] == ["fp1", "fp2", "fp3"]

    @pytest.mark.asyncio
    async def test_compare_versions(self, versioning_service: VersioningService) -> None:
        """Test comparing two versions of a document."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        await versioning_service.create_version(doc_id, {"fingerprint": "fp1", "chunks_added": 10}, session)
        await versioning_service.create_version(doc_id, {"fingerprint": "fp2", "chunks_added": 15}, session)

        diff = await versioning_service.compare_versions(doc_id, 1, 2, session)
        assert isinstance(diff, VersionDiff)
        assert diff.version_a == 1
        assert diff.version_b == 2
        assert diff.fingerprint_changed is True

    @pytest.mark.asyncio
    async def test_version_diff_summary(self, versioning_service: VersioningService) -> None:
        """Test that version diff includes a human-readable summary."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        await versioning_service.create_version(doc_id, {"fingerprint": "same"}, session)
        await versioning_service.create_version(doc_id, {"fingerprint": "same"}, session)

        diff = await versioning_service.compare_versions(doc_id, 1, 2, session)
        assert "no content change" in diff.summary

    @pytest.mark.asyncio
    async def test_compare_nonexistent_versions(self, versioning_service: VersioningService) -> None:
        """Test comparing versions that don't exist raises ValueError."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        with pytest.raises(ValueError, match=r"Version\(s\) not found"):
            await versioning_service.compare_versions(doc_id, 1, 2, session)

    @pytest.mark.asyncio
    async def test_version_increment(self, versioning_service: VersioningService) -> None:
        """Test that versions increment correctly."""
        doc_id = uuid4()
        doc = self._make_doc_mock(metadata={})
        session = self._make_session(doc)

        v1 = await versioning_service.create_version(doc_id, {}, session)
        v2 = await versioning_service.create_version(doc_id, {}, session)
        v3 = await versioning_service.create_version(doc_id, {}, session)

        assert v1.change_type == "created"
        assert v2.change_type == "updated"
        assert v3.change_type == "updated"
        assert v3.version == 3

    @pytest.mark.asyncio
    async def test_separate_documents(self, versioning_service: VersioningService) -> None:
        """Test that different documents have independent version histories."""
        doc_a = uuid4()
        doc_b = uuid4()

        doc_a_mock = self._make_doc_mock(metadata={})
        doc_b_mock = self._make_doc_mock(metadata={})
        session_a = self._make_session(doc_a_mock)
        session_b = self._make_session(doc_b_mock)

        await versioning_service.create_version(doc_a, {"fingerprint": "a1"}, session_a)
        await versioning_service.create_version(doc_b, {"fingerprint": "b1"}, session_b)

        history_a = await versioning_service.get_version_history(doc_a, session_a)
        history_b = await versioning_service.get_version_history(doc_b, session_b)

        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0].document_id != history_b[0].document_id
