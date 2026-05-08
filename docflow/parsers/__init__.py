"""Document parsers and parser registry."""

from docflow.parsers.base import BaseParser, ParsedDocument, Section
from docflow.parsers.markdown import MarkdownParser
from docflow.parsers.html import HTMLParser
from docflow.parsers.pdf import PDFParser
from docflow.parsers.docx import DocxParser
from docflow.parsers.csv import CSVParser

_parsers: dict[str, type[BaseParser]] = {
    "md": MarkdownParser,
    "html": HTMLParser,
    "htm": HTMLParser,
    "pdf": PDFParser,
    "docx": DocxParser,
    "csv": CSVParser,
}


def get_parser(file_type: str) -> BaseParser:
    """Get the appropriate parser for a file type.

    Args:
        file_type: File extension (e.g., 'md', 'pdf', 'html').

    Returns:
        An instance of the matching parser.

    Raises:
        ValueError: If no parser is registered for the file type.
    """
    parser_class = _parsers.get(file_type)
    if parser_class is None:
        raise ValueError(f"No parser registered for file type: {file_type}")
    return parser_class()


__all__ = ["BaseParser", "ParsedDocument", "Section", "get_parser"]
