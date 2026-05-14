"""Source management API endpoints."""

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.config import settings
from docflow.db import get_session
from docflow.db.models import Document, Source, SourceCreate, SourceResponse
from docflow.queue.redis_queue import RedisQueue

router = APIRouter(prefix="/api/sources", tags=["sources"])

SUPPORTED_EXTENSIONS = {"md", "pdf", "html", "htm", "docx", "csv"}


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    payload: SourceCreate,
    session: AsyncSession = Depends(get_session),
) -> Source:
    """Create a new document source."""
    source = Source(name=payload.name, type=payload.type, config=payload.config)
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


@router.get("", response_model=dict[str, Any])
async def list_sources(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List all configured sources."""
    result = await session.execute(select(Source))
    sources = result.scalars().all()
    return {"sources": [SourceResponse.model_validate(s) for s in sources], "total": len(sources)}


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Source:
    """Get a specific source by ID."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a source by ID."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await session.delete(source)
    await session.commit()


@router.post("/{source_id}/sync", response_model=dict[str, Any])
async def sync_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Trigger synchronization of a source.

    Scans the source directory for new or changed documents and queues them
    for processing. Currently supports local sources only.
    """
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    if source.type != "local":
        return {"status": "unsupported", "source_id": str(source_id), "message": f"Sync not implemented for source type: {source.type}"}

    config = source.config or {}
    source_path = config.get("path", "")
    if not source_path:
        return {"status": "error", "source_id": str(source_id), "message": "Source has no path configured"}

    base = Path(source_path)
    if not base.exists():
        raise HTTPException(status_code=400, detail=f"Source path not found: {source_path}")

    documents_created = 0
    queue = RedisQueue()
    await queue.connect()

    try:
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lstrip(".").lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            existing = await session.execute(
                select(Document).where(
                    Document.source_id == source_id,
                    Document.file_path == str(file_path),
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            doc = Document(
                title=file_path.name,
                file_path=str(file_path),
                file_type=ext,
                source_id=source_id,
                status="pending",
            )
            session.add(doc)
            await session.flush()
            await queue.enqueue(
                f"{settings.QUEUE_NAME}:ingest",
                {"document_id": str(doc.id)},
            )
            documents_created += 1

        await session.commit()
    finally:
        await queue.disconnect()

    return {
        "status": "sync_complete",
        "source_id": str(source_id),
        "source_path": source_path,
        "documents_created": documents_created,
    }
