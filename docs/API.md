# API Reference

Base URL: `http://localhost:8000`

## Sources

### Create Source

```bash
curl -X POST http://localhost:8000/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "company-wiki",
    "type": "local",
    "config": {"path": "./data/sample"}
  }'
```

**Response** `201 Created`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "company-wiki",
  "type": "local",
  "config": {"path": "./data/sample"},
  "status": "active",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### List Sources

```bash
curl http://localhost:8000/api/sources
```

**Response** `200 OK`:
```json
{
  "sources": [
    {"id": "...", "name": "company-wiki", "type": "local", "status": "active", "...": "..."}
  ],
  "total": 1
}
```

### Get Source

```bash
curl http://localhost:8000/api/sources/{source_id}
```

### Delete Source

```bash
curl -X DELETE http://localhost:8000/api/sources/{source_id}
```

### Trigger Source Sync

```bash
curl -X POST http://localhost:8000/api/sources/{source_id}/sync
```

## Documents

### Upload Documents

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "files=@data/sample/company_handbook.md" \
  -F "files=@data/sample/product_docs.md" \
  -F "source_id=550e8400-e29b-41d4-a716-446655440000"
```

**Response** `201 Created`:
```json
{
  "uploaded": [
    {"id": "...", "title": "company_handbook.md", "status": "pending"}
  ],
  "errors": []
}
```

### List Documents

```bash
curl "http://localhost:8000/api/documents?status=ready&file_type=md&limit=20&offset=0"
```

**Query parameters**: `status`, `file_type`, `source_id`, `limit`, `offset`

### Get Document

```bash
curl http://localhost:8000/api/documents/{document_id}
```

**Response** includes document metadata and chunk summary (not full chunk content).

### Delete Document

```bash
curl -X DELETE http://localhost:8000/api/documents/{document_id}
```

### Re-index Document

```bash
curl -X POST http://localhost:8000/api/documents/{document_id}/reindex
```

### Get Document Versions

```bash
curl http://localhost:8000/api/documents/{document_id}/versions
```

## Pipeline

### Pipeline Status

```bash
curl http://localhost:8000/api/pipeline/status
```

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "queues": {
    "ingest": {"pending": 3, "processing": 1},
    "embed": {"pending": 5, "processing": 2}
  },
  "stats": {
    "documents_total": 150,
    "documents_ready": 142,
    "documents_error": 3,
    "chunks_total": 4500
  }
}
```

### List Processing Jobs

```bash
curl "http://localhost:8000/api/pipeline/jobs?status=error&limit=20"
```

### Retry Failed Job

```bash
curl -X POST http://localhost:8000/api/pipeline/retry/{job_id}
```

## Health

### Health Check

```bash
curl http://localhost:8000/api/health
```

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "redis": "connected"
}
```
