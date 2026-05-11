"""Document management API endpoints."""

import os
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.config import settings
from docflow.db import get_session
from docflow.db.models import Chunk, Document, DocumentResponse
from docflow.processing.versioning import VersioningService
from docflow.queue.redis_queue import RedisQueue
from docflow.storage.object_store import ObjectStore

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS: set[str] = {"md", "pdf", "html", "docx", "csv", "txt"}


@router.post("/upload", status_code=201)
async def upload_documents(
    files: list[UploadFile] = File(...),
    source_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upload one or more documents for processing.

    Files are stored via the ObjectStore and queued for ingestion.
    """
    uploaded: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    store = ObjectStore()
    queue = RedisQueue()
    await queue.connect()

    try:
        for file in files:
            ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({"filename": file.filename or "unknown", "error": f"Unsupported file type: {ext}"})
                continue

            max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            content = await file.read()
            if len(content) > max_bytes:
                errors.append({"filename": file.filename or "unknown", "error": "File exceeds size limit"})
                continue

            stored_name = f"{uuid.uuid4().hex}.{ext}"
            file_path = await store.save(stored_name, content)

            doc = Document(
                title=file.filename or stored_name,
                file_path=file_path,
                file_type=ext,
                source_id=source_id,
                status="pending",
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            await queue.enqueue(
                f"{settings.QUEUE_NAME}:ingest",
                {"document_id": str(doc.id)},
            )

            uploaded.append({"id": str(doc.id), "title": doc.title, "status": "pending"})

    finally:
        await queue.disconnect()

    return {"uploaded": uploaded, "errors": errors}


@router.get("")
async def list_documents(
    status: str | None = None,
    file_type: str | None = None,
    source_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List documents with optional filters."""
    query = select(Document)
    count_query = select(func.count()).select_from(Document)

    if status:
        query = query.where(Document.status == status)
        count_query = count_query.where(Document.status == status)
    if file_type:
        query = query.where(Document.file_type == file_type)
        count_query = count_query.where(Document.file_type == file_type)
    if source_id:
        query = query.where(Document.source_id == source_id)
        count_query = count_query.where(Document.source_id == source_id)

    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    documents = result.scalars().all()

    return {
        "documents": [DocumentResponse.model_validate(d) for d in documents],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get a document with its chunk summary."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = (
        await session.execute(select(func.count()).where(Chunk.document_id == document_id))
    ).scalar() or 0

    response = DocumentResponse.model_validate(doc)
    return {**response.model_dump(), "chunk_count": chunk_count}


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a document and its associated chunks."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.delete(doc)
    await session.commit()


@router.post("/{document_id}/reindex", response_model=dict[str, str])
async def reindex_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Trigger re-indexing of a document."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "pending"
    await session.commit()

    queue = RedisQueue()
    await queue.connect()
    try:
        await queue.enqueue(
            f"{settings.QUEUE_NAME}:ingest",
            {"document_id": str(document_id)},
        )
    finally:
        await queue.disconnect()

    return {"status": "reindex_started", "document_id": str(document_id)}


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get the version history of a document."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    versioning_service = VersioningService()
    history = versioning_service.get_version_history(document_id, session)

    return {
        "document_id": str(document_id),
        "current_version": doc.version,
        "versions": [v.model_dump() for v in history],
    }
