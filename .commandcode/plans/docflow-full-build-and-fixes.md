# DocFlow — Full Build & Issue Fix Plan

## Issues Found & Fixes Required

### 1. CRITICAL: `docflow/db/__init__.py` is broken
**Problem**: 
- Line 1 imports from `docflow.db.session` which doesn't exist
- Line 4 has orphaned text `clarativeBase` that breaks syntax
- Uses `create_async_engine`, `async_sessionmaker`, `AsyncSession`, `DeclarativeBase`, `AsyncGenerator` with no imports whatsoever

**Fix**: Rewrite `docflow/db/__init__.py` completely — remove the bogus `from docflow.db.session import ...`, remove `clarativeBase`, add all missing imports:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from docflow.config import settings
```

### 2. `docflow/main.py` imports from nonexistent `docflow.db.session`
**Problem**: Line 11: `from docflow.db.session import init_db` — `session` module doesn't exist.

**Fix**: Change to `from docflow.db import init_db`.

### 3. `docflow/api/router.py` has self-referential import
**Problem**: `docflow/api/router.py` contains only `from docflow.api.router import api_router` — it imports itself.

**Fix**: The router aggregation code actually lives in `docflow/api/__init__.py`. Move that code into `docflow/api/router.py` and have `__init__.py` re-export:

- `docflow/api/router.py` → contains the actual `api_router` aggregation (the code currently in `__init__.py`)
- `docflow/api/__init__.py` → `from docflow.api.router import api_router` (re-export only)

### 4. No `Dockerfile`
**Problem**: `docker-compose.yml` has `build: .` for 3 services but no Dockerfile exists.

**Fix**: Create `Dockerfile`.

### 5. Workers are stubs — full implementation needed
**Problem**: `IngestWorker._load_document` returns `None`, `_update_status`, `_store_fingerprint`, `_store_metadata`, `_store_chunks` are all no-ops. `EmbedWorker._load_chunks` returns `[]`, `_store_vectors` is a no-op. Neither worker has a `__main__` entry point.

**Fix for `IngestWorker`**:
- `_load_document`: Query DB via async session
- `_update_status`: Update Document.status + commit
- `_store_fingerprint`: Set Document.content_hash + Document.fingerprint + commit
- `_store_metadata`: Merge metadata into Document.metadata_ + commit
- `_store_chunks`: Create Chunk records in DB + commit
- `process_document`: Accept AsyncSession parameter
- `__main__`: Connect to DB + Redis, loop dequeuing and processing

**Fix for `EmbedWorker`**:
- `_load_chunks`: Query DB for chunks via async session
- `_store_vectors`: Update chunk.embedding column + commit
- `__main__`: Connect to DB + Redis, loop dequeuing and processing

### 6. CLI commands are stubs — full implementation needed
**Problem**: All 6 Typer commands print placeholder messages without any actual service integration.

**Fix**: Implement async helpers with DB + queue integration:
- `_ingest`: Walk path → filter supported files → create Document records → enqueue
- `_show_status`: Query DB for doc counts, queue depths
- `_list_docs`: Query DB with filters, display as table
- `_reindex_source/_reindex_document`: Set status to 'pending' + enqueue
- `_compare`: Call VersioningService.compare_versions()
- `_cleanup`: Delete orphaned chunks + old processing jobs

### 7. No Alembic migration versions
**Problem**: `alembic/versions/` directory doesn't exist.

**Fix**: Create `alembic/versions/` directory and write `001_initial.py` migration.

### 8. Health check is hardcoded
**Problem**: Always returns "connected" without actual checks.

**Fix**: Add real DB + Redis connection checks.

### 9. Source sync endpoint is stub
**Problem**: `sync_source` returns "sync_started" but doesn't scan or queue.

**Fix**: Implement local source scanning, create Document records, enqueue jobs.

### 10. Test file `test_pipeline.py` missing `Path` import
**Problem**: Uses `tmp_path: "Path"` but Path never imported.

**Fix**: Add `from pathlib import Path`.

### 11. Dangling imports at bottom of worker files
**Problem**: `from typing import Any` at bottom of both worker files.

**Fix**: Move to top of files.

### 12. Document upload doesn't use ObjectStore or enqueue jobs
**Problem**: Raw file writes, no job enqueueing.

**Fix**: Use ObjectStore.save(), enqueue to Redis after document creation.
