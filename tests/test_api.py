"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from docflow.main import app
from docflow.config import settings
from docflow.db import engine

client = TestClient(app)


def _db_available() -> bool:
    """Check if the configured database is reachable."""
    import asyncio

    async def check() -> bool:
        from sqlalchemy import text

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False

    return asyncio.run(check())


db_required = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL database not available",
)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self) -> None:
        """Test that the health endpoint returns 200 with status info."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "version" in data
        assert "database" in data
        assert "redis" in data

    def test_root_endpoint(self) -> None:
        """Test that the root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "DocFlow"
        assert data["status"] == "running"


@db_required
class TestSourceEndpoints:
    """Tests for source management endpoints."""

    def test_create_source(self) -> None:
        """Test creating a new source."""
        response = client.post(
            "/api/sources",
            json={"name": "test-source", "type": "local", "config": {"path": "./data"}},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-source"
        assert data["type"] == "local"

    def test_list_sources(self) -> None:
        """Test listing sources."""
        response = client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "total" in data

    def test_get_source_not_found(self) -> None:
        """Test getting a non-existent source returns 404."""
        response = client.get("/api/sources/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


@db_required
class TestDocumentEndpoints:
    """Tests for document management endpoints."""

    def test_list_documents(self) -> None:
        """Test listing documents."""
        response = client.get("/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data

    def test_get_document_not_found(self) -> None:
        """Test getting a non-existent document returns 404."""
        response = client.get("/api/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_delete_document_not_found(self) -> None:
        """Test deleting a non-existent document returns 404."""
        response = client.delete("/api/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_reindex_document_not_found(self) -> None:
        """Test re-indexing a non-existent document returns 404."""
        response = client.post("/api/documents/00000000-0000-0000-0000-000000000000/reindex")
        assert response.status_code == 404


@db_required
class TestPipelineEndpoints:
    """Tests for pipeline monitoring endpoints."""

    def test_pipeline_status(self) -> None:
        """Test getting pipeline status."""
        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "stats" in data

    def test_list_jobs(self) -> None:
        """Test listing processing jobs."""
        response = client.get("/api/pipeline/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data

    def test_retry_job_not_found(self) -> None:
        """Test retrying a non-existent job returns 404."""
        response = client.post("/api/pipeline/retry/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
