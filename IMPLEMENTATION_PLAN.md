# Implementation Plan

## Phase 1 - Core

Goal: Working end-to-end pipeline with minimal dependencies.

### API Endpoints
- POST /api/sources (create source)
- POST /api/documents/upload (upload documents)
- GET /api/documents (list documents)
- GET /api/documents/{id} (get document with chunks)
- GET /api/pipeline/status (pipeline health)

### Parsers
- MarkdownParser: frontmatter extraction, header-based sections
- HTMLParser: content extraction with BeautifulSoup, boilerplate removal

### Chunking
- Fixed-size chunking with configurable overlap
- Sentence-based chunking with max size constraint

### Storage
- SQLite for development (via SQLAlchemy async)
- Local filesystem object store
- In-memory vector store (flat list with cosine similarity)

### Processing
- Synchronous processing (no queue in phase 1)
- Basic fingerprinting (SHA-256 content hash)
- Simple deduplication by fingerprint match

### Tests
- Parser unit tests
- Chunking unit tests
- Basic API tests

## Phase 2 - Intelligence

Goal: Production-grade processing with all features.

### Queue System
- Redis-based job queue
- IngestWorker: dequeues documents, runs full pipeline
- EmbedWorker: dequeues chunks, generates embeddings
- Job status tracking in database

### All Parsers
- PDFParser: PyMuPDF text extraction with page metadata
- DocxParser: python-docx with styles and tables
- CSVParser: delimiter detection, row-based chunking

### Fingerprinting & Deduplication
- SHA-256 content fingerprinting
- File-level hash for binary comparison
- Content similarity check for near-duplicates
- Chunk-level deduplication

### Versioning
- Document version creation on content change
- Version history retrieval
- Version diff comparison

### Embedding
- OpenAI embeddings integration
- Sentence-transformers fallback
- Batch embedding with rate limiting
- pgvector storage

### Database
- PostgreSQL with pgvector extension
- Alembic migrations
- All models with proper indexes

### Tests
- Deduplication tests
- Versioning tests
- Full pipeline integration tests
- Worker tests with mock queue

## Phase 3 - Polish

Goal: Production readiness and operational tooling.

### CLI Admin Tool
- `docflow ingest --path <path>`: Trigger document ingestion
- `docflow reindex --source <id>`: Re-index a source
- `docflow status`: Show pipeline status
- `docflow list-docs`: List documents with filters
- `docflow compare-versions --doc <id> --v1 <n> --v2 <n>`: Compare versions
- `docflow cleanup`: Remove orphaned records

### Batch Operations
- Bulk document upload
- Batch re-indexing
- Bulk delete with cascade

### Monitoring
- Processing metrics (throughput, error rate, latency)
- Queue depth monitoring
- Storage usage tracking

### Failure Recovery
- Dead letter queue inspection
- Failed job retry with backoff
- Partial processing recovery
- Orphan cleanup

### Deployment
- Production docker-compose with health checks
- Worker autoscaling configuration
- Database connection pooling
- Logging and structured output
