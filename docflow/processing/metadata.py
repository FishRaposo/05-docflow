"""Document metadata extraction and normalization."""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Normalized metadata extracted from a document."""

    title: str = Field(default="", description="Document title")
    language: str = Field(default="en", description="Detected language code")
    author: str = Field(default="", description="Document author")
    word_count: int = Field(default=0, description="Total word count")
    character_count: int = Field(default=0, description="Total character count")
    estimated_read_time_minutes: int = Field(default=0, description="Estimated reading time")
    detected_dates: list[str] = Field(default_factory=list, description="Dates found in content")
    file_size_bytes: int = Field(default=0, description="File size in bytes")


class MetadataExtractor:
    """Extracts and normalizes metadata from documents.

    Provides language detection, date extraction, word counting,
    and reading time estimation.
    """

    def extract_metadata(self, file_path: str, content: str) -> DocumentMetadata:
        """Extract normalized metadata from a document.

        Args:
            file_path: Path to the source file.
            content: Parsed text content of the document.

        Returns:
            DocumentMetadata with extracted and computed fields.
        """
        word_count = len(content.split())
        char_count = len(content)
        dates = self._extract_dates(content)
        language = self._detect_language(content)
        read_time = self._estimate_read_time(word_count)
        file_size = self._get_file_size(file_path)

        return DocumentMetadata(
            word_count=word_count,
            character_count=char_count,
            detected_dates=dates,
            language=language,
            estimated_read_time_minutes=read_time,
            file_size_bytes=file_size,
        )

    def _detect_language(self, content: str) -> str:
        """Detect the language of text content using simple heuristics.

        Uses common word patterns for basic language detection. Falls back
        to 'en' if detection is inconclusive.

        Args:
            content: Text content to analyze.

        Returns:
            ISO 639-1 language code string.
        """
        if not content:
            return "en"

        common_en = {"the", "is", "and", "that", "have", "for", "not", "with", "this", "are"}
        common_pt = {"de", "que", "não", "em", "um", "uma", "para", "com", "os", "as"}
        common_es = {"de", "que", "el", "en", "un", "una", "para", "con", "los", "las"}

        words = set(content.lower().split())

        en_score = len(words & common_en)
        pt_score = len(words & common_pt)
        es_score = len(words & common_es)

        scores = {"en": en_score, "pt": pt_score, "es": es_score}
        best = max(scores, key=lambda k: scores[k])

        if scores[best] >= 2:
            return best
        return "en"

    def _extract_dates(self, content: str) -> list[str]:
        """Extract date-like strings from text content.

        Finds dates in common formats (ISO, US, European).

        Args:
            content: Text content to search for dates.

        Returns:
            List of date strings found in the content.
        """
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}/\d{2}/\d{4}",
            r"\d{2}\.\d{2}\.\d{4}",
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
        ]
        dates: list[str] = []
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            dates.extend(matches)
        return dates

    def _estimate_read_time(self, word_count: int) -> int:
        """Estimate reading time in minutes based on word count.

        Assumes an average reading speed of 200 words per minute.

        Args:
            word_count: Number of words in the document.

        Returns:
            Estimated reading time in whole minutes (minimum 1).
        """
        if word_count == 0:
            return 0
        return max(1, word_count // 200)

    def _get_file_size(self, file_path: str) -> int:
        """Get the file size in bytes.

        Args:
            file_path: Path to the file.

        Returns:
            File size in bytes, or 0 if the file cannot be accessed.
        """
        try:
            from pathlib import Path

            return Path(file_path).stat().st_size
        except (OSError, FileNotFoundError):
            return 0
