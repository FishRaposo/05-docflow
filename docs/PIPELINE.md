# Pipeline

## Pipeline Flow

Documents enter the pipeline through the API and flow through discrete processing stages. Each stage has a clear input/output contract and can fail independently.

## Stages

### 1. Upload / Source Ingestion

**Input**: File bytes + metadata from HTTP upload or source sync
**Output**: Document record in `pending` status, file stored in object store
**Side effects**: File written to disk, database record created

### 2. Parse

**Input**: File path from document record
**Output**: `ParsedDocument` with content, metadata, sections, and raw text
**Error handling**: Parser not found for file type → mark document as `error`

### 3. Fingerprint

**Input**: Parsed text content
**Output**: SHA-256 fingerprint string
**Side effects**: Fingerprint stored on document record

### 4. Deduplication

**Input**: Document fingerprint
**Output**: Duplicate status (new, exact duplicate, near duplicate)
**Behavior**:
- Exact duplicate → skip processing, link to existing document
- Near duplicate → create new version of existing document
- New → proceed with chunking

### 5. Metadata Extraction

**Input**: File path, parsed content
**Output**: Normalized `DocumentMetadata` (language, dates, read time, etc.)
**Side effects**: Metadata merged into document record

### 6. Chunking

**Input**: Parsed text content (or sections for structural chunking)
**Output**: List of `ChunkCandidate` with content, position, and metadata
**Configuration**: Strategy, chunk size, overlap

### 7. Version Check

**Input**: Document ID, new fingerprint
**Output**: New version record if content changed
**Behavior**: Only creates new version when fingerprint differs from current

### 8. Embedding

**Input**: List of chunk texts
**Output**: List of embedding vectors
**Behavior**: Batch processing with rate limiting, configurable model

### 9. Storage

**Input**: Chunks with embeddings
**Output**: Records written to PostgreSQL + pgvector
**Side effects**: Document status updated to `ready`

## Error Handling Per Stage

| Stage | Possible Failures | Recovery |
|---|---|---|
| Upload | File too large, unsupported type | Return 400 with details |
| Parse | Corrupt file, encoding issues | Mark document `error`, log details |
| Fingerprint | Empty content | Skip fingerprint, flag for review |
| Dedup | Database connection | Retry 3x, then move to DLQ |
| Metadata | NLP library error | Use defaults, log warning |
| Chunking | Empty text after parse | Mark document `error` |
| Embedding | API rate limit, model error | Retry with backoff, batch fallback |
| Storage | Database error | Retry transaction, preserve chunks |
