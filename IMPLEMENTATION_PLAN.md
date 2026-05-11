# Implementation Plan

## Phase 1 - Core

Goal: Working end-to-end pipeline with minimal dependencies.

### API Endpoints
- [x] POST /api/sources (create source)
- [x] POST /api/documents/upload (upload documents)
- [x] GET /api/documents (list documents)
- [x] GET /api/documents/{id} (get document with chunks)
- [x] GET /api/pipeline/status (pipeline health)

### Parsers
- [x] MarkdownParser: frontmatter extraction, header-based sections
- [x] HTMLParser: content extraction with BeautifulSoup, boilerplate removal

### Chunking
- [x] Fixed-size chunking with configurable overlap
- [x] Sentence-based chunking with max size constraint

### Storage
- [x] SQLite for development (via SQLAlchemy async)
- [x] Local filesystem object store
- [x] In-memory vector store (flat list with cosine similarity)

### Processing
- [x] Synchronous processing (no queue in phase 1)
- [x] Basic fingerprinting (SHA-256 content hash)
- [x] Simple deduplication by fingerprint match

### Tests
- [x] Parser unit tests
- [x] Chunking unit tests
- [x] Basic API tests

## Phase 2 - Intelligence

Goal: Production-grade processing with all features.

### Queue System
- [x] Redis-based job queue
- [x] IngestWorker: dequeues documents, runs full pipeline
- [x] EmbedWorker: dequeues chunks, generates embeddings
- [x] Job status tracking in database

### All Parsers
- [x] PDFParser: PyMuPDF text extraction with page metadata
- [x] DocxParser: python-docx with styles and tables
- [x] CSVParser: delimiter detection, row-based chunking

### Fingerprinting & Deduplication
- [x] SHA-256 content fingerprinting
- [x] File-level hash for binary comparison
- [x] Content similarity check for near-duplicates
- [x] Chunk-level deduplication

### Versioning
- [x] Document version creation on content change
- [x] Version history retrieval
- [x] Version diff comparison

### Embedding
- [x] OpenAI embeddings integration
- [x] Sentence-transformers fallback
- [x] Batch embedding with rate limiting
- [x] pgvector storage

### Database
- [x] PostgreSQL with pgvector extension
- [x] Alembic migrations
- [x] All models with proper indexes

### Tests
- [x] Deduplication tests
- [x] Versioning tests
- [x] Full pipeline integration tests
- [x] Worker tests with mock queue

## Phase 3 - Polish

Goal: Production readiness and operational tooling.

### CLI Admin Tool
- [x] `docflow ingest --path <path>`: Trigger document ingestion
- [x] `docflow reindex --source <id>`: Re-index a source
- [x] `docflow status`: Show pipeline status
- [x] `docflow list-docs`: List documents with filters
- [x] `docflow compare-versions --doc <id> --v1 <n> --v2 <n>`: Compare versions
- [x] `docflow cleanup`: Remove orphaned records

### Batch Operations
- [x] Bulk document upload
- [x] Batch re-indexing
- [x] Bulk delete with cascade

### Monitoring
- [x] Processing metrics (throughput, error rate, latency)
- [x] Queue depth monitoring
- [x] Storage usage tracking

### Failure Recovery
- [x] Dead letter queue inspection
- [x] Failed job retry with backoff
- [x] Partial processing recovery
- [x] Orphan cleanup

### Deployment
- [x] Production docker-compose with health checks
- [x] Worker autoscaling configuration
- [x] Database connection pooling
- [x] Logging and structured output
