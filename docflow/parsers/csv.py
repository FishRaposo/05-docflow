"""CSV document parser with delimiter detection and row chunking."""

import csv
import io

from docflow.parsers.base import BaseParser, ParsedDocument, Section


class CSVParser(BaseParser):
    """Parser for CSV files with automatic delimiter detection and row-based chunking.

    Converts tabular data into text suitable for embedding, preserving
    headers and row structure.
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a CSV file into structured content.

        Args:
            file_path: Path to the .csv file.

        Returns:
            ParsedDocument with row-based sections and column metadata.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        delimiter = self._detect_delimiter(raw_text)
        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return ParsedDocument(content="", raw_text=raw_text, file_type="csv")

        headers = rows[0]
        data_rows = rows[1:]
        sections = self._chunk_rows(headers, data_rows)

        content_parts: list[str] = []
        for section in sections:
            content_parts.append(section.content)
        full_content = "\n\n".join(content_parts)

        return ParsedDocument(
            content=full_content,
            metadata={
                "columns": headers,
                "row_count": len(data_rows),
                "delimiter": delimiter,
            },
            sections=sections,
            raw_text=raw_text,
            title=f"CSV Data ({len(headers)} columns, {len(data_rows)} rows)",
            file_type="csv",
        )

    def _detect_delimiter(self, text: str) -> str:
        """Detect the delimiter used in CSV text.

        Uses csv.Sniffer to auto-detect, falling back to comma.

        Args:
            text: Raw CSV text.

        Returns:
            Detected delimiter character.
        """
        try:
            dialect = csv.Sniffer().sniff(text[:4096])
            return dialect.delimiter
        except csv.Error:
            return ","

    def _chunk_rows(self, headers: list[str], rows: list[list[str]], chunk_size: int = 50) -> list[Section]:
        """Group rows into chunks of configurable size.

        Each chunk includes the header row for context.

        Args:
            headers: Column header names.
            rows: Data rows.
            chunk_size: Maximum rows per chunk.

        Returns:
            List of Section objects, each containing a row group.
        """
        sections: list[Section] = []
        header_line = " | ".join(headers)

        for i in range(0, len(rows), chunk_size):
            chunk_rows = rows[i : i + chunk_size]
            lines = [header_line]
            for row in chunk_rows:
                lines.append(" | ".join(row))
            content = "\n".join(lines)
            sections.append(
                Section(
                    title=f"Rows {i + 1}-{i + len(chunk_rows)}",
                    level=1,
                    content=content,
                    start_char=0,
                    end_char=len(content),
                )
            )

        return sections
