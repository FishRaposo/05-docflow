---
title: DocFlow Product Documentation
author: Engineering Team
version: "2.0"
---

# DocFlow Product Documentation

DocFlow is a production-style document ingestion pipeline designed for RAG (Retrieval-Augmented Generation) and knowledge management systems.

## Overview

DocFlow automates the process of ingesting documents from various sources, parsing them into structured content, chunking them intelligently, and preparing them for vector-based retrieval. It handles the full document lifecycle including versioning, deduplication, and metadata extraction.

## Key Features

### Multi-Format Parsing

DocFlow supports parsing documents in multiple formats:

- **Markdown**: Full frontmatter support, header-based sections
- **PDF**: Page-by-page extraction with metadata
- **HTML**: Content extraction with boilerplate removal
- **DOCX**: Paragraph styles and table extraction
- **CSV**: Automatic delimiter detection and row-based chunking

### Intelligent Chunking

Choose from multiple chunking strategies based on your content type:

1. **Fixed-size**: Simple character-based splitting with overlap
2. **Sentence-based**: Splits at sentence boundaries for coherence
3. **Semantic**: Groups related sentences by topic similarity
4. **Structural**: Uses document headings and sections

### Deduplication

DocFlow uses SHA-256 content fingerprinting to detect exact duplicates. Near-duplicate detection uses similarity scoring to identify documents that are substantially similar but not identical.

### Versioning

Every document change creates a new version. Compare versions to see what changed, and maintain a complete audit trail of content evolution.

## Architecture

DocFlow uses a queue-based architecture with two worker types:

- **Ingest Workers**: Handle parsing, fingerprinting, deduplication, and chunking
- **Embed Workers**: Generate embeddings and store vectors

This separation allows independent scaling of compute-intensive operations.

## Configuration

Configure DocFlow through environment variables:

- `CHUNK_SIZE`: Default chunk size in characters (default: 512)
- `CHUNK_OVERLAP`: Overlap between consecutive chunks (default: 64)
- `CHUNKING_STRATEGY`: Default strategy (fixed, sentence, semantic, structure)
- `EMBEDDING_MODEL`: Model for generating embeddings
- `WORKER_CONCURRENCY`: Number of concurrent workers

## API Endpoints

### Sources

- `POST /api/sources` - Create a new document source
- `GET /api/sources` - List all sources
- `GET /api/sources/{id}` - Get source details
- `DELETE /api/sources/{id}` - Delete a source
- `POST /api/sources/{id}/sync` - Trigger source synchronization

### Documents

- `POST /api/documents/upload` - Upload documents for processing
- `GET /api/documents` - List documents with filters
- `GET /api/documents/{id}` - Get document details
- `DELETE /api/documents/{id}` - Delete a document
- `POST /api/documents/{id}/reindex` - Re-index a document

### Pipeline

- `GET /api/pipeline/status` - Pipeline health and statistics
- `GET /api/pipeline/jobs` - List processing jobs
- `POST /api/pipeline/retry/{job_id}` - Retry a failed job

## Deployment

### Docker Compose

The recommended deployment method is Docker Compose:

```bash
docker compose up -d
```

This starts the API server, ingest workers, embed workers, PostgreSQL with pgvector, and Redis.

### Scaling Workers

Scale workers independently based on load:

```bash
docker compose up -d --scale worker-ingest=3 --scale worker-embed=2
```

## Best Practices

### Chunk Size Selection

- **Small chunks (128-256 chars)**: Better for precise retrieval, may lose context
- **Medium chunks (512 chars)**: Good balance for most use cases
- **Large chunks (1024+ chars)**: More context, may dilute relevance

### Source Organization

Organize your sources by content type or department. This enables targeted filtering during retrieval and makes it easier to manage access controls.

### Monitoring

Monitor the pipeline status endpoint regularly. Watch for:
- Growing queue depths (indicates worker bottleneck)
- High error rates (may indicate parser issues)
- Stale documents (may need re-indexing)

## Troubleshooting

### Documents Stuck in Processing

Check the processing jobs endpoint for failed jobs. Common causes include:
- Unsupported file format
- Corrupt file
- File exceeds size limit
- Parser error

### Poor Retrieval Quality

If search results aren't relevant:
1. Check your chunking strategy - try a different one
2. Adjust chunk size and overlap
3. Ensure metadata is being extracted correctly
4. Verify embeddings are being generated

## Changelog

### v2.0 (2024-03-01)
- Added semantic chunking strategy
- Improved HTML parser with better boilerplate removal
- Added version comparison API
- Performance improvements for large documents

### v1.0 (2024-01-15)
- Initial release
- Basic parsing for Markdown, PDF, HTML, DOCX, CSV
- Fixed-size and sentence chunking
- SHA-256 fingerprinting and deduplication
- PostgreSQL + pgvector storage
