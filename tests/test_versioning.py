"""Tests for document versioning service."""

from uuid import uuid4

import pytest

from docflow.processing.versioning import VersioningService, VersionDiff


class TestVersioningService:
    """Tests for the versioning service."""

    def test_create_version(self, versioning_service: VersioningService) -> None:
        """Test creating a first version for a document."""
        doc_id = uuid4()
        version = versioning_service.create_version(doc_id, {"fingerprint": "abc123"})

        assert version.document_id == doc_id
        assert version.version == 1
        assert version.fingerprint == "abc123"
        assert version.change_type == "created"

    def test_version_history(self, versioning_service: VersioningService) -> None:
        """Test retrieving the full version history."""
        doc_id = uuid4()
        versioning_service.create_version(doc_id, {"fingerprint": "fp1"})
        versioning_service.create_version(doc_id, {"fingerprint": "fp2"})
        versioning_service.create_version(doc_id, {"fingerprint": "fp3"})

        history = versioning_service.get_version_history(doc_id)
        assert len(history) == 3
        assert [v.version for v in history] == [1, 2, 3]

    def test_compare_versions(self, versioning_service: VersioningService) -> None:
        """Test comparing two versions of a document."""
        doc_id = uuid4()
        versioning_service.create_version(doc_id, {"fingerprint": "fp1", "chunks_added": 10})
        versioning_service.create_version(doc_id, {"fingerprint": "fp2", "chunks_added": 15})

        diff = versioning_service.compare_versions(doc_id, 1, 2)
        assert isinstance(diff, VersionDiff)
        assert diff.version_a == 1
        assert diff.version_b == 2
        assert diff.fingerprint_changed is True

    def test_version_diff_summary(self, versioning_service: VersioningService) -> None:
        """Test that version diff includes a human-readable summary."""
        doc_id = uuid4()
        versioning_service.create_version(doc_id, {"fingerprint": "same"})
        versioning_service.create_version(doc_id, {"fingerprint": "same"})

        diff = versioning_service.compare_versions(doc_id, 1, 2)
        assert "no content change" in diff.summary

    def test_compare_nonexistent_versions(self, versioning_service: VersioningService) -> None:
        """Test comparing versions that don't exist raises ValueError."""
        doc_id = uuid4()
        with pytest.raises(ValueError, match="Version\\(s\\) not found"):
            versioning_service.compare_versions(doc_id, 1, 2)

    def test_version_increment(self, versioning_service: VersioningService) -> None:
        """Test that versions increment correctly."""
        doc_id = uuid4()
        v1 = versioning_service.create_version(doc_id, {})
        v2 = versioning_service.create_version(doc_id, {})
        v3 = versioning_service.create_version(doc_id, {})

        assert v1.change_type == "created"
        assert v2.change_type == "updated"
        assert v3.change_type == "updated"
        assert v3.version == 3

    def test_separate_documents(self, versioning_service: VersioningService) -> None:
        """Test that different documents have independent version histories."""
        doc_a = uuid4()
        doc_b = uuid4()
        versioning_service.create_version(doc_a, {"fingerprint": "a1"})
        versioning_service.create_version(doc_b, {"fingerprint": "b1"})

        history_a = versioning_service.get_version_history(doc_a)
        history_b = versioning_service.get_version_history(doc_b)

        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0].document_id != history_b[0].document_id
