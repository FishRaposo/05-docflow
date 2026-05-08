"""Integration tests for the full document processing pipeline."""

import pytest

from docflow.parsers.markdown import MarkdownParser
from docflow.parsers.html import HTMLParser
from docflow.parsers.csv import CSVParser
from docflow.processing.chunking import ChunkingService
from docflow.processing.deduplication import DeduplicationService
from docflow.processing.fingerprint import Fingerprinter
from docflow.processing.metadata import MetadataExtractor
from docflow.processing.versioning import VersioningService


class TestFullPipeline:
    """Integration tests running the full document processing pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_markdown(self, sample_markdown_content: str, tmp_path: "Path") -> None:
        """Test the full pipeline with a markdown document."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown_content)

        parser = MarkdownParser()
        fingerprinter = Fingerprinter()
        metadata_extractor = MetadataExtractor()
        chunker = ChunkingService(chunk_size=200, chunk_overlap=20)
        versioning_service = VersioningService()

        parsed = await parser.parse(str(md_file))
        assert len(parsed.content) > 0

        fingerprint = fingerprinter.compute_fingerprint(parsed.content)
        assert len(fingerprint) == 64

        metadata = metadata_extractor.extract_metadata(str(md_file), parsed.content)
        assert metadata.word_count > 0

        chunks = chunker.chunk_fixed(parsed.content)
        assert len(chunks) > 0

        version = versioning_service.create_version(
            md_file.stat().st_uid if hasattr(md_file.stat(), "st_uid") else 0,
            {"fingerprint": fingerprint},
        )
        assert version.version == 1

    @pytest.mark.asyncio
    async def test_full_pipeline_with_dedup(
        self,
        sample_markdown_content: str,
        tmp_path: "Path",
    ) -> None:
        """Test pipeline deduplication when processing the same document twice."""
        md_file = tmp_path / "dup_test.md"
        md_file.write_text(sample_markdown_content)

        parser = MarkdownParser()
        fingerprinter = Fingerprinter()
        dedup_service = DeduplicationService()

        from uuid import uuid4

        doc_id = uuid4()

        parsed = await parser.parse(str(md_file))
        fingerprint = fingerprinter.compute_fingerprint(parsed.content)

        result1 = dedup_service.check_content_duplicate(fingerprint)
        assert result1.is_duplicate is False
        dedup_service.register_fingerprint(fingerprint, doc_id)

        result2 = dedup_service.check_content_duplicate(fingerprint)
        assert result2.is_duplicate is True
        assert result2.existing_id == doc_id

    @pytest.mark.asyncio
    async def test_pipeline_failure_recovery(self, tmp_path: "Path") -> None:
        """Test that the pipeline handles and recovers from processing failures."""
        parser = MarkdownParser()
        non_existent = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            await parser.parse(str(non_existent))

    @pytest.mark.asyncio
    async def test_pipeline_versioning(self, sample_markdown_content: str, tmp_path: "Path") -> None:
        """Test that multiple processing runs create version history."""
        md_file = tmp_path / "versioned.md"
        md_file.write_text(sample_markdown_content)

        from uuid import uuid4

        doc_id = uuid4()
        fingerprinter = Fingerprinter()
        versioning_service = VersioningService()

        parsed = await MarkdownParser().parse(str(md_file))
        fp = fingerprinter.compute_fingerprint(parsed.content)
        v1 = versioning_service.create_version(doc_id, {"fingerprint": fp})

        md_file.write_text(sample_markdown_content + "\n\n# New Section\n\nNew content.")
        parsed2 = await MarkdownParser().parse(str(md_file))
        fp2 = fingerprinter.compute_fingerprint(parsed2.content)
        v2 = versioning_service.create_version(doc_id, {"fingerprint": fp2})

        assert v1.version == 1
        assert v2.version == 2

        diff = versioning_service.compare_versions(doc_id, 1, 2)
        assert diff.fingerprint_changed is True
