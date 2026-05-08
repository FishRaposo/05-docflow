# Chunking Strategies

Chunking is the process of splitting a parsed document into smaller pieces suitable for embedding and retrieval. The quality of chunking directly impacts retrieval quality.

## Available Strategies

### Fixed-Size Chunking

Splits text into chunks of a fixed character count with optional overlap.

**When to use**: General-purpose, works well for homogeneous text like articles and reports.

**Configuration**:
- `CHUNK_SIZE`: Number of characters per chunk (default: 512)
- `CHUNK_OVERLAP`: Number of overlapping characters between chunks (default: 64)

**Example**:
```
Text of 1000 chars with CHUNK_SIZE=300, CHUNK_OVERLAP=50:
  Chunk 0: chars 0-300
  Chunk 1: chars 250-550
  Chunk 2: chars 500-800
  Chunk 3: chars 750-1000
```

### Sentence-Based Chunking

Splits text at sentence boundaries, grouping sentences until the maximum size is reached.

**When to use**: When preserving sentence coherence matters, such as legal or technical documents.

**Configuration**:
- `CHUNK_SIZE`: Maximum characters per chunk (default: 512)

**Behavior**:
- Splits text into sentences using punctuation heuristics
- Groups sentences into chunks that don't exceed the max size
- Never splits a sentence in half

### Semantic Chunking

Groups text by semantic similarity, creating chunks of topically related content.

**When to use**: When documents cover diverse topics and you want each chunk to be thematically coherent.

**Configuration**:
- `threshold`: Similarity threshold for grouping (default: 0.7)

**Behavior**:
- Splits text into sentences
- Computes embeddings for each sentence
- Groups consecutive sentences with similarity above threshold
- Falls back to sentence-based chunking if embeddings are unavailable

### Structural Chunking

Uses document structure (headers, sections) to create chunks.

**When to use**: When documents have clear structure (markdown headers, HTML sections, document chapters).

**Configuration**: None needed; structure is detected from the parsed document sections.

**Behavior**:
- Uses sections extracted by the parser
- Each section becomes a chunk
- Subsections are nested within parent sections
- Very large sections may be split using fixed-size strategy

## Chunk Metadata

Each chunk includes metadata for retrieval filtering and context reconstruction:

| Field | Type | Description |
|---|---|---|
| `chunk_index` | int | Position in the document (0-based) |
| `start_char` | int | Starting character position in source text |
| `end_char` | int | Ending character position in source text |
| `section` | str or None | Section header if structural chunking |
| `page` | int or None | Page number for PDF documents |
| `token_count` | int or None | Estimated token count |

## Selecting a Strategy

```python
# General purpose
CHUNKING_STRATEGY=fixed CHUNK_SIZE=512 CHUNK_OVERLAP=64

# Coherent sentences
CHUNKING_STRATEGY=sentence CHUNK_SIZE=512

# Topic-aware
CHUNKING_STRATEGY=semantic

# Structured documents (markdown, HTML)
CHUNKING_STRATEGY=structure
```
