"""Tests for text chunking strategies."""

import pytest

from docflow.processing.chunking import ChunkingService, ChunkCandidate


class TestFixedChunking:
    """Tests for fixed-size chunking strategy."""

    def test_fixed_chunking_size(self, chunking_service: ChunkingService) -> None:
        """Test that chunks respect the configured size."""
        text = "A" * 300
        chunks = chunking_service.chunk_fixed(text, size=100, overlap=0)

        for chunk in chunks:
            assert len(chunk.content) <= 100

    def test_fixed_chunking_overlap(self) -> None:
        """Test that overlap creates shared content between consecutive chunks."""
        service = ChunkingService(chunk_size=50, chunk_overlap=10)
        text = "A" * 200
        chunks = service.chunk_fixed(text, size=50, overlap=10)

        assert len(chunks) > 1
        for i in range(1, len(chunks)):
            prev_end = chunks[i - 1].end_char
            curr_start = chunks[i].start_char
            assert curr_start < prev_end

    def test_fixed_chunking_empty_text(self, chunking_service: ChunkingService) -> None:
        """Test that empty text produces no chunks."""
        chunks = chunking_service.chunk_fixed("")
        assert chunks == []

    def test_fixed_chunking_short_text(self, chunking_service: ChunkingService) -> None:
        """Test that text shorter than chunk size produces one chunk."""
        text = "Short text"
        chunks = chunking_service.chunk_fixed(text, size=100, overlap=0)

        assert len(chunks) == 1
        assert chunks[0].content == "Short text"

    def test_fixed_chunking_positions(self, chunking_service: ChunkingService) -> None:
        """Test that start_char and end_char are correctly set."""
        text = "A" * 200
        chunks = chunking_service.chunk_fixed(text, size=80, overlap=0)

        assert chunks[0].start_char == 0
        assert chunks[-1].end_char == 200


class TestSentenceChunking:
    """Tests for sentence-based chunking strategy."""

    def test_sentence_chunking(self, chunking_service: ChunkingService) -> None:
        """Test that text is split at sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        chunks = chunking_service.chunk_by_sentence(text, max_size=50)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 100

    def test_sentence_chunking_max_size(self) -> None:
        """Test that no chunk exceeds the maximum size."""
        service = ChunkingService(chunk_size=30)
        text = "This is a short sentence. Another one here. And a third for good measure."
        chunks = service.chunk_by_sentence(text, max_size=30)

        for chunk in chunks:
            assert len(chunk.content) <= 60

    def test_sentence_chunking_empty(self, chunking_service: ChunkingService) -> None:
        """Test that empty text produces no chunks."""
        chunks = chunking_service.chunk_by_sentence("")
        assert chunks == []

    def test_sentence_chunking_single_sentence(self, chunking_service: ChunkingService) -> None:
        """Test that a single sentence produces one chunk."""
        text = "Just one sentence here."
        chunks = chunking_service.chunk_by_sentence(text)

        assert len(chunks) == 1


class TestSemanticChunking:
    """Tests for semantic chunking strategy."""

    def test_semantic_chunking_placeholder(self, chunking_service: ChunkingService) -> None:
        """Test semantic chunking produces results (falls back to sentence-based)."""
        text = "Topic A is about cats. Cats are furry animals. Topic B is about dogs. Dogs are loyal companions."
        chunks = chunking_service.chunk_by_semantic(text, threshold=0.7)

        assert len(chunks) > 0
        full_content = " ".join(c.content for c in chunks)
        assert "cats" in full_content.lower()
        assert "dogs" in full_content.lower()


class TestStructureChunking:
    """Tests for structural chunking strategy."""

    def test_structure_chunking(self, chunking_service: ChunkingService) -> None:
        """Test that sections map to chunks correctly."""
        from docflow.parsers.base import Section

        sections = [
            Section(title="Intro", level=1, content="A" * 50, start_char=0, end_char=50),
            Section(title="Body", level=1, content="B" * 50, start_char=50, end_char=100),
            Section(title="End", level=1, content="C" * 50, start_char=100, end_char=150),
        ]

        chunks = chunking_service.chunk_by_structure(sections)
        assert len(chunks) == 3
        assert chunks[0].metadata["section_title"] == "Intro"
        assert chunks[1].metadata["section_title"] == "Body"

    def test_structure_chunking_large_section(self) -> None:
        """Test that large sections are further split with fixed chunking."""
        from docflow.parsers.base import Section

        service = ChunkingService(chunk_size=50, chunk_overlap=0)
        sections = [
            Section(title="Big", level=1, content="X" * 200, start_char=0, end_char=200),
        ]

        chunks = service.chunk_by_structure(sections)
        assert len(chunks) > 1
        assert all("section_title" in c.metadata for c in chunks)
