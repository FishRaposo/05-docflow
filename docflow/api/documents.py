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
from docflow.db.models import Document, DocumentResponse

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS: set[str] = {"md", "pdf", "html", "docx", "csv", "txt"}


@router.post("/upload", status_code=201)
async def upload_documents(
    files: list[UploadFile] = File(...),
    source_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upload one or more documents for processing.

    Files are stored in the configured storage path and queued for ingestion.

    Args:
        files: List of files to upload.
        source_id: Optional parent source UUID.
        session: Async database session.

    Returns:
        Dictionary with uploaded documents and any errors.
    """
    uploaded: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

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

        os.makedirs(settings.STORAGE_PATH, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(settings.STORAGE_PATH, stored_name)
        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            title=file.filename or stored_name,
            file_path=file_path,
            file_type=ext,
            source_id=source_id,
            status="pending",
        )
        session.add(doc)
        uploaded.append({"id": str(doc.id), "title": doc.title, "status": "pending"})

    await session.commit()
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
    """List documents with optional filters.

    Args:
        status: Filter by processing status.
        file_type: Filter by file extension.
        source_id: Filter by parent source.
        limit: Maximum number of results.
        offset: Number of results to skip.
        session: Async database session.

    Returns:
        Paginated list of documents.
    """
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
    """Get a document with its chunk summary.

    Args:
        document_id: UUID of the document to retrieve.
        session: Async database session.

    Returns:
        Document details with chunk count.

    Raises:
        HTTPException: 404 if document not found.
    """
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    from docflow.db.models import Chunk

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
    """Delete a document and its associated chunks.

    Args:
        document_id: UUID of the document to delete.
        session: Async database session.

    Raises:
        HTTPException: 404 if document not found.
    """
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
    """Trigger re-indexing of a document.

    Re-runs the full ingestion pipeline on an existing document.

    Args:
        document_id: UUID of the document to re-index.
        session: Async database session.

    Returns:
        Status message confirming re-index was triggered.

    Raises:
        HTTPException: 404 if document not found.
    """
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "pending"
    await session.commit()
    return {"status": "reindex_started", "document_id": str(document_id)}


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get the version history of a document.

    Args:
        document_id: UUID of the document.
        session: Async database session.

    Returns:
        List of document versions.

    Raises:
        HTTPException: 404 if document not found.
    """
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": str(document_id),
        "current_version": doc.version,
        "versions": [{"version": doc.version, "fingerprint": doc.fingerprint}],
    }
