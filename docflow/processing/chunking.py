"""Text chunking service with multiple strategies."""

import re
from typing import Any

from pydantic import BaseModel, Field

from docflow.config import settings
from docflow.parsers.base import Section


class ChunkCandidate(BaseModel):
    """A candidate chunk produced by a chunking strategy."""

    content: str = Field(description="Chunk text content")
    start_char: int = Field(default=0, description="Start position in source text")
    end_char: int = Field(default=0, description="End position in source text")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class ChunkingService:
    """Service for splitting text into chunks using configurable strategies.

    Supports fixed-size, sentence-based, section-size, and structural chunking.
    """

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ) -> None:
        """Initialize the chunking service.

        Args:
            chunk_size: Default chunk size in characters.
            chunk_overlap: Default overlap between chunks in characters.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_fixed(
        self,
        text: str,
        size: int | None = None,
        overlap: int | None = None,
    ) -> list[ChunkCandidate]:
        """Split text into fixed-size chunks with optional overlap.

        Args:
            text: Text to chunk.
            size: Chunk size in characters (defaults to configured value).
            overlap: Overlap in characters (defaults to configured value).

        Returns:
            List of ChunkCandidate objects.
        """
        size = size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        step = max(1, size - overlap)

        if not text:
            return []

        chunks: list[ChunkCandidate] = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    ChunkCandidate(
                        content=chunk_text,
                        start_char=start,
                        end_char=end,
                        metadata={"strategy": "fixed", "chunk_size": size},
                    )
                )
            start += step

        return chunks

    def chunk_by_sentence(
        self,
        text: str,
        max_size: int | None = None,
    ) -> list[ChunkCandidate]:
        """Split text into chunks at sentence boundaries.

        Groups sentences until the maximum size is reached. Never splits
        a sentence in half.

        Args:
            text: Text to chunk.
            max_size: Maximum chunk size in characters.

        Returns:
            List of ChunkCandidate objects.
        """
        max_size = max_size or self.chunk_size
        if not text:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[ChunkCandidate] = []
        current_lines: list[str] = []
        current_start = 0
        current_len = 0

        for sentence in sentences:
            if current_len + len(sentence) > max_size and current_lines:
                content = " ".join(current_lines)
                chunks.append(
                    ChunkCandidate(
                        content=content,
                        start_char=current_start,
                        end_char=current_start + len(content),
                        metadata={"strategy": "sentence"},
                    )
                )
                current_lines = []
                current_start += current_len + 1
                current_len = 0

            current_lines.append(sentence)
            current_len += len(sentence) + 1

        if current_lines:
            content = " ".join(current_lines)
            chunks.append(
                ChunkCandidate(
                    content=content,
                    start_char=current_start,
                    end_char=current_start + len(content),
                    metadata={"strategy": "sentence"},
                )
            )

        return chunks

    def chunk_by_section_size(
        self,
        text: str,
        threshold: float = 0.7,
    ) -> list[ChunkCandidate]:
        """Split text into chunks grouped by character count.

        Groups consecutive sentences until chunk_size is reached, then
        starts a new group. The threshold parameter is accepted for API
        compatibility but does not affect the grouping logic.

        Args:
            text: Text to chunk.
            threshold: Ignored; accepted for API compatibility.

        Returns:
            List of ChunkCandidate objects.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 1:
            return self.chunk_by_sentence(text)

        chunks: list[ChunkCandidate] = []
        current_group: list[str] = [sentences[0]]
        pos = 0

        for i in range(1, len(sentences)):
            current_group.append(sentences[i])

            if len(" ".join(current_group)) > self.chunk_size:
                content = " ".join(current_group[:-1])
                chunks.append(
                    ChunkCandidate(
                        content=content,
                        start_char=pos,
                        end_char=pos + len(content),
                        metadata={"strategy": "section_size", "threshold": threshold},
                    )
                )
                pos += len(content) + 1
                current_group = [sentences[i]]

        if current_group:
            content = " ".join(current_group)
            chunks.append(
                ChunkCandidate(
                    content=content,
                    start_char=pos,
                    end_char=pos + len(content),
                    metadata={"strategy": "section_size", "threshold": threshold},
                )
            )

        return chunks

    def chunk_by_structure(self, sections: list[Section]) -> list[ChunkCandidate]:
        """Split document into chunks based on structural sections.

        Each section becomes one or more chunks. Large sections are
        further split using fixed-size chunking.

        Args:
            sections: List of document sections from the parser.

        Returns:
            List of ChunkCandidate objects.
        """
        chunks: list[ChunkCandidate] = []

        for section in sections:
            if len(section.content) <= self.chunk_size:
                chunks.append(
                    ChunkCandidate(
                        content=section.content,
                        start_char=section.start_char,
                        end_char=section.end_char,
                        metadata={
                            "strategy": "structure",
                            "section_title": section.title,
                            "section_level": section.level,
                        },
                    )
                )
            else:
                sub_chunks = self.chunk_fixed(section.content)
                for sub in sub_chunks:
                    sub.metadata.update(
                        {
                            "strategy": "structure+fixed",
                            "section_title": section.title,
                            "section_level": section.level,
                        }
                    )
                chunks.extend(sub_chunks)

        return chunks
