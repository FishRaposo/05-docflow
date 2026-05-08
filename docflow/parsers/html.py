"""HTML document parser with content extraction and cleaning."""

from bs4 import BeautifulSoup, Tag

from docflow.parsers.base import BaseParser, ParsedDocument, Section


class HTMLParser(BaseParser):
    """Parser for HTML files with boilerplate removal and content extraction.

    Uses BeautifulSoup to parse HTML, extract the main content area, and
    produce clean text with structural sections based on heading tags.
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse an HTML file into structured content.

        Args:
            file_path: Path to the .html file.

        Returns:
            ParsedDocument with extracted content and heading-based sections.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            raw_html = f.read()

        soup = BeautifulSoup(raw_html, "html.parser")
        main_content = self._extract_main_content(soup)
        cleaned_text = self._clean_html(main_content)
        sections = self._extract_sections(main_content)

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        metadata: dict = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name", "")
            content_attr = meta.get("content", "")
            if name and content_attr:
                metadata[name] = content_attr

        return ParsedDocument(
            content=cleaned_text,
            metadata=metadata,
            sections=sections,
            raw_text=raw_html,
            title=title,
            file_type="html",
        )

    def _extract_main_content(self, soup: BeautifulSoup) -> Tag:
        """Extract the main content area from HTML, removing boilerplate.

        Checks for semantic HTML5 tags first, then falls back to body.

        Args:
            soup: Parsed BeautifulSoup document.

        Returns:
            Tag containing the main content.
        """
        for selector in ["main", "article", '[role="main"]', "#content", ".content"]:
            result = soup.select_one(selector)
            if result:
                return result
        return soup.body if soup.body else soup

    def _clean_html(self, tag: Tag) -> str:
        """Convert HTML tag to clean text, removing scripts, styles, and nav.

        Args:
            tag: BeautifulSoup Tag to clean.

        Returns:
            Cleaned text content.
        """
        for element in tag.find_all(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        return tag.get_text(separator="\n", strip=True)

    def _extract_sections(self, tag: Tag) -> list[Section]:
        """Extract sections from HTML based on heading tags (h1-h6).

        Args:
            tag: BeautifulSoup Tag to extract sections from.

        Returns:
            List of Section objects based on heading hierarchy.
        """
        sections: list[Section] = []
        current_title = ""
        current_level = 1
        current_lines: list[str] = []
        pos = 0

        for child in tag.descendants:
            if isinstance(child, Tag):
                if child.name and child.name.startswith("h") and child.name[1:].isdigit():
                    if current_lines:
                        sections.append(
                            Section(
                                title=current_title,
                                level=current_level,
                                content="\n".join(current_lines).strip(),
                                start_char=pos,
                                end_char=pos + sum(len(l) for l in current_lines),
                            )
                        )
                    current_title = child.get_text(strip=True)
                    current_level = int(child.name[1])
                    current_lines = []
                elif child.name in ("p", "li", "td", "span"):
                    text = child.get_text(strip=True)
                    if text:
                        current_lines.append(text)
                        pos += len(text)

        if current_lines:
            sections.append(
                Section(
                    title=current_title,
                    level=current_level,
                    content="\n".join(current_lines).strip(),
                    start_char=pos,
                    end_char=pos + sum(len(l) for l in current_lines),
                )
            )

        return sections
