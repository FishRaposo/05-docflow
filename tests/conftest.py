"""Pytest fixtures and test configuration."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

from docflow.processing.chunking import ChunkingService
from docflow.processing.deduplication import DeduplicationService
from docflow.processing.embedding import EmbeddingService
from docflow.processing.fingerprint import Fingerprinter
from docflow.processing.metadata import MetadataExtractor
from docflow.processing.versioning import VersioningService


SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_dir() -> Path:
    """Provide the path to sample data files."""
    return SAMPLE_DIR


@pytest.fixture
def sample_markdown_content() -> str:
    """Provide sample markdown content for testing."""
    return """---
title: Test Document
author: Test Author
---

# Introduction

This is a test document with multiple sections for testing the document ingestion pipeline.

## Getting Started

To get started with DocFlow, you need to configure your environment variables and start the services.

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Redis server

## Configuration

The configuration is managed through environment variables. Copy the .env.example file to .env and update the values.

## Usage

Upload documents via the API or CLI. The pipeline will automatically parse, chunk, and embed the content.

# Advanced Topics

## Custom Parsers

You can implement custom parsers by extending the BaseParser class.

## Chunking Strategies

Multiple chunking strategies are available: fixed, sentence, semantic, and structural.
"""


@pytest.fixture
def sample_html_content() -> str:
    """Provide sample HTML content for testing."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="author" content="Test Author">
    <script>console.log('should be removed');</script>
    <style>body { margin: 0; }</style>
</head>
<body>
    <header>Navigation bar</header>
    <main>
        <h1>Main Title</h1>
        <p>This is the first paragraph of the main content.</p>
        <h2>Section One</h2>
        <p>Content for section one with some details.</p>
        <h2>Section Two</h2>
        <p>Content for section two with more information.</p>
    </main>
    <footer>Footer content</footer>
</body>
</html>"""


@pytest.fixture
def sample_csv_content() -> str:
    """Provide sample CSV content for testing."""
    return """name,department,salary,startDate
Alice,Engineering,95000,2024-01-15
Bob,Marketing,78000,2024-02-01
Charlie,Engineering,102000,2023-11-20
Diana,HR,85000,2024-03-10
Eve,Sales,72000,2024-01-05
Frank,Engineering,98000,2023-09-15"""


@pytest.fixture
def chunking_service() -> ChunkingService:
    """Provide a ChunkingService instance with default settings."""
    return ChunkingService(chunk_size=100, chunk_overlap=20)


@pytest.fixture
def fingerprinter() -> Fingerprinter:
    """Provide a Fingerprinter instance."""
    return Fingerprinter()


@pytest.fixture
def deduplication_service() -> DeduplicationService:
    """Provide a fresh DeduplicationService instance."""
    return DeduplicationService()


@pytest.fixture
def versioning_service() -> VersioningService:
    """Provide a fresh VersioningService instance."""
    return VersioningService()


@pytest.fixture
def metadata_extractor() -> MetadataExtractor:
    """Provide a MetadataExtractor instance."""
    return MetadataExtractor()


@pytest.fixture
def mock_embedding_service() -> EmbeddingService:
    """Provide an EmbeddingService instance (uses local/placeholder mode)."""
    return EmbeddingService()
