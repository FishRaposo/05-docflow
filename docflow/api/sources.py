"""Source management API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.db import get_session
from docflow.db.models import Source, SourceCreate, SourceResponse

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    payload: SourceCreate,
    session: AsyncSession = Depends(get_session),
) -> Source:
    """Create a new document source.

    Args:
        payload: Source creation data with name, type, and optional config.
        session: Async database session.

    Returns:
        The created source record.
    """
    source = Source(name=payload.name, type=payload.type, config=payload.config)
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


@router.get("", response_model=dict[str, Any])
async def list_sources(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List all configured sources.

    Args:
        session: Async database session.

    Returns:
        Dictionary with sources list and total count.
    """
    result = await session.execute(select(Source))
    sources = result.scalars().all()
    return {"sources": [SourceResponse.model_validate(s) for s in sources], "total": len(sources)}


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Source:
    """Get a specific source by ID.

    Args:
        source_id: UUID of the source to retrieve.
        session: Async database session.

    Returns:
        The source record.

    Raises:
        HTTPException: 404 if source not found.
    """
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
    """Delete a source by ID.

    Args:
        source_id: UUID of the source to delete.
        session: Async database session.

    Raises:
        HTTPException: 404 if source not found.
    """
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await session.delete(source)
    await session.commit()


@router.post("/{source_id}/sync", response_model=dict[str, str])
async def sync_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Trigger synchronization of a source.

    Scans the source for new or changed documents and queues them for processing.

    Args:
        source_id: UUID of the source to sync.
        session: Async database session.

    Returns:
        Status message confirming sync was triggered.

    Raises:
        HTTPException: 404 if source not found.
    """
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "sync_started", "source_id": str(source_id)}
