"""PDF document parser using PyMuPDF."""

from docflow.parsers.base import BaseParser, ParsedDocument, Section


class PDFParser(BaseParser):
    """Parser for PDF files using PyMuPDF for text extraction.

    Extracts text page by page, collects PDF metadata, and creates
    page-based sections.
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a PDF file into structured content.

        Args:
            file_path: Path to the .pdf file.

        Returns:
            ParsedDocument with page-based sections and PDF metadata.
        """
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF is required for PDF parsing: pip install PyMuPDF")

        doc = fitz.open(file_path)
        metadata = self._extract_metadata(doc)
        pages_text: list[str] = []
        sections: list[Section] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            cleaned = self._clean_text(text)
            pages_text.append(cleaned)
            pos = sum(len(p) for p in pages_text[:-1])
            sections.append(
                Section(
                    title=f"Page {page_num + 1}",
                    level=1,
                    content=cleaned,
                    start_char=pos,
                    end_char=pos + len(cleaned),
                )
            )

        doc.close()
        full_content = "\n\n".join(pages_text)
        title = metadata.get("title", file_path.split("/")[-1])

        return ParsedDocument(
            content=full_content,
            metadata=metadata,
            sections=sections,
            raw_text=full_content,
            title=title,
            file_type="pdf",
        )

    def _extract_metadata(self, doc: Any) -> dict[str, Any]:
        """Extract metadata from a PDF document.

        Args:
            doc: PyMuPDF document object.

        Returns:
            Dictionary of PDF metadata fields.
        """
        meta = doc.metadata or {}
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "page_count": len(doc),
        }

    def _clean_text(self, text: str) -> str:
        """Clean extracted PDF text by normalizing whitespace and removing artifacts.

        Args:
            text: Raw text extracted from a PDF page.

        Returns:
            Cleaned text with normalized whitespace.
        """
        lines = text.split("\n")
        cleaned_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
        return "\n".join(cleaned_lines)


from typing import Any
