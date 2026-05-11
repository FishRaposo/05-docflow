# Contributing to DocFlow

## Getting started

```bash
# Clone the repo
git clone <repo-url> && cd docflow

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install in development mode
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Copy environment config
cp .env.example .env
```

## Development workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run tests: `pytest`
4. Run linting: `ruff check docflow/ tests/ && mypy docflow`
5. Run formatting: `ruff format docflow/ tests/`
6. Commit and push

## Running services

```bash
# Start PostgreSQL, Redis, and related services
docker compose up -d

# Run database migrations
alembic upgrade head

# Start a worker
python -m docflow.workers.ingest_worker
python -m docflow.workers.embed_worker
```

## Project structure

```
docflow/
  admin/         CLI tools (Typer)
  api/           FastAPI routes and middleware
  db/            SQLAlchemy models and session management
  parsers/       Document format parsers (DOCX, MD, HTML, CSV, etc.)
  processing/    Core pipeline logic (chunking, fingerprinting, dedup, etc.)
  queue/         Redis queue abstraction and DLQ
  storage/       Object store and vector store abstractions
  workers/       Async worker processes
tests/           Test suite
```

## Code style

- Python 3.11+ with type annotations everywhere
- Ruff for linting and formatting (replaces flake8, isort, black)
- Mypy for static type checking (strict mode for new code)
- Docstrings follow Google style
- Async/await throughout the pipeline

## Adding a new parser

1. Create a new module in `docflow/parsers/` (e.g., `pdf_parser.py`)
2. Implement the `BaseParser` interface with an `async def parse(self, file_path: str) -> ParsedDocument` method
3. Register the parser in `docflow/parsers/__init__.py` in the `get_parser` function
4. Add tests in `tests/` using sample fixtures

## Adding a chunking strategy

1. Add a new method to `ChunkingService` in `docflow/processing/chunking.py`
2. Add a new strategy name to the configuration options
3. Wire it up in `IngestWorker.process_document`
4. Test with varied document sizes and content types

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=docflow --cov-report=html

# Run specific test files
pytest tests/test_chunking.py -v
pytest tests/test_deduplication.py -v

# Run specific test class or method
pytest tests/test_versioning.py::TestVersioningService::test_create_version -v
```

## Database migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `OPENAI_API_KEY` | (empty) | OpenAI API key for embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model name |
| `EMBEDDING_DIMENSIONS` | `1536` | Embedding vector dimensions |
| `CHUNK_SIZE` | `512` | Default chunk size in characters |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `CHUNKING_STRATEGY` | `fixed` | Chunking strategy |
| `QUEUE_NAME` | `docflow` | Redis queue base name |
| `STORAGE_BACKEND` | `local` | Storage backend (`local` or `s3`) |
| `STORAGE_PATH` | `./data/uploads` | Local storage path |
