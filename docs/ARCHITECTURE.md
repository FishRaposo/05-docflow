# Architecture

## System Overview

DocFlow is a document ingestion pipeline built around a queue-based worker architecture. Documents flow through discrete processing stages, each with clear input/output contracts and independent failure handling.

```mermaid
graph TB
    subgraph "API Layer"
        A[FastAPI Server]
        A1[REST Endpoints]
        A2[CLI Admin Tool]
    end

    subgraph "Queue Layer"
        Q[Redis Queue]
    end

    subgraph "Worker Layer"
        W1[Ingest Worker]
        W2[Embed Worker]
    end

    subgraph "Processing Layer"
        P1[Parsers]
        P2[Fingerprinter]
        P3[Deduplicator]
        P4[Chunker]
        P5[Metadata Extractor]
        P6[Versioning]
    end

    subgraph "Storage Layer"
        DB[(PostgreSQL + pgvector)]
        OS[Object Store]
        VS[Vector Store]
    end

    A1 --> Q
    A2 --> Q
    Q --> W1
    Q --> W2
    W1 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
    W2 --> VS
    W1 --> DB
    W2 --> DB
    P1 --> OS
```

## Pipeline Stages

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Queue
    participant IngestWorker
    participant Parser
    participant Fingerprinter
    participant Deduplicator
    participant Chunker
    participant EmbedWorker
    participant VectorStore
    participant Database

    Client->>API: Upload document
    API->>Database: Create document record
    API->>Queue: Enqueue ingest job
    API-->>Client: Return document ID

    Queue->>IngestWorker: Dequeue job
    IngestWorker->>Parser: Parse file
    Parser-->>IngestWorker: ParsedDocument
    IngestWorker->>Fingerprinter: Compute fingerprint
    Fingerprinter-->>IngestWorker: SHA-256 hash
    IngestWorker->>Deduplicator: Check for duplicates
    Deduplicator-->>IngestWorker: Duplicate status
    IngestWorker->>Chunker: Split into chunks
    Chunker-->>IngestWorker: Chunk candidates
    IngestWorker->>Database: Store chunks
    IngestWorker->>Queue: Enqueue embed job

    Queue->>EmbedWorker: Dequeue embed job
    EmbedWorker->>VectorStore: Generate embeddings
    VectorStore-->>EmbedWorker: Embeddings
    EmbedWorker->>Database: Store vectors
```

## Service Interactions

### API Service
- Accepts document uploads and source configurations
- Creates database records and enques processing jobs
- Returns processing status and query results

### Ingest Worker
- Dequeues documents from the ingest queue
- Runs the full parse → fingerprint → dedup → chunk pipeline
- Updates document status at each stage
- Enqueues embed jobs for successfully processed documents

### Embed Worker
- Dequeues embed jobs from the embed queue
- Generates embeddings using configured model
- Stores vectors in pgvector
- Handles rate limiting and batch processing

## Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| API Framework | FastAPI | Async, type-safe, auto-docs |
| Database | PostgreSQL + pgvector | Relational + vector in one store |
| Queue | Redis | Fast, simple, widely supported |
| ORM | SQLAlchemy 2.0 | Async support, typed queries |
| Validation | Pydantic v2 | Fast, JSON Schema, settings |
| PDF Parsing | PyMuPDF | Fast, no external deps |
| HTML Parsing | BeautifulSoup | Robust, forgiving parser |
| Markdown | python-markdown + frontmatter | Metadata + rendering |
| Embeddings | OpenAI / sentence-transformers | Cloud or local options |
