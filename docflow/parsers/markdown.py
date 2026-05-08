"""Markdown document parser with frontmatter and section extraction."""

from docflow.parsers.base import BaseParser, ParsedDocument, Section


class MarkdownParser(BaseParser):
    """Parser for Markdown files with frontmatter and header-based sections.

    Extracts YAML frontmatter metadata and splits the document into sections
    based on markdown headers (#, ##, ###, etc.).
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a Markdown file into structured content.

        Args:
            file_path: Path to the .md file.

        Returns:
            ParsedDocument with frontmatter metadata and header-based sections.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        metadata, content = self._extract_frontmatter(raw_text)
        sections = self._split_sections(content)
        title = metadata.get("title", "")

        if not title and sections:
            title = sections[0].title

        return ParsedDocument(
            content=content,
            metadata=metadata,
            sections=sections,
            raw_text=raw_text,
            title=title,
            file_type="md",
        )

    def _extract_frontmatter(self, text: str) -> tuple[dict, str]:
        """Extract YAML frontmatter from markdown text.

        Args:
            text: Raw markdown text potentially containing frontmatter.

        Returns:
            Tuple of (metadata dict, remaining content string).
        """
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        frontmatter_text = parts[1].strip()
        content = parts[2].strip()

        metadata: dict = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip().strip('"').strip("'")

        return metadata, content

    def _split_sections(self, content: str) -> list[Section]:
        """Split markdown content into sections based on headers.

        Args:
            content: Markdown text without frontmatter.

        Returns:
            List of Section objects, one per header-delimited section.
        """
        sections: list[Section] = []
        current_title = ""
        current_level = 1
        current_lines: list[str] = []
        current_start = 0
        pos = 0

        for line in content.split("\n"):
            stripped = line.lstrip("#")
            level = len(line) - len(stripped)

            if level > 0 and line.startswith("#"):
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    sections.append(
                        Section(
                            title=current_title,
                            level=current_level,
                            content=body,
                            start_char=current_start,
                            end_char=pos - 1,
                        )
                    )
                current_title = stripped.strip()
                current_level = level
                current_lines = []
                current_start = pos
            else:
                current_lines.append(line)

            pos += len(line) + 1

        if current_lines:
            body = "\n".join(current_lines).strip()
            sections.append(
                Section(
                    title=current_title,
                    level=current_level,
                    content=body,
                    start_char=current_start,
                    end_char=pos - 1,
                )
            )

        return sections
