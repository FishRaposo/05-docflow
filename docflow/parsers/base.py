"""Abstract base parser and parsed document model."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class Section(BaseModel):
    """A structural section within a parsed document."""

    title: str = Field(description="Section heading or title")
    level: int = Field(default=1, description="Heading level (1-6)")
    content: str = Field(description="Section body text")
    start_char: int = Field(default=0, description="Start position in full text")
    end_char: int = Field(default=0, description="End position in full text")


class ParsedDocument(BaseModel):
    """Normalized output from any document parser."""

    content: str = Field(description="Full document text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extracted metadata")
    sections: list[Section] = Field(default_factory=list, description="Structural sections")
    raw_text: str = Field(default="", description="Original raw text before processing")
    title: str = Field(default="", description="Document title")
    file_type: str = Field(default="", description="Source file type extension")


class BaseParser(ABC):
    """Abstract base class for document parsers.

    Each file format should implement this interface to produce a consistent
    ParsedDocument output regardless of the input format.
    """

    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a file into a normalized ParsedDocument.

        Args:
            file_path: Path to the file to parse.

        Returns:
            ParsedDocument with content, metadata, and sections.
        """
        ...
