"""Pipeline monitoring and management API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.db import get_session
from docflow.db.models import Document, ProcessingJob, ProcessingJobResponse

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/status")
async def pipeline_status(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get pipeline health and processing statistics.

    Returns overall pipeline status including queue depths and document counts.

    Args:
        session: Async database session.

    Returns:
        Pipeline health status and statistics.
    """
    total_docs = (await session.execute(select(func.count()).select_from(Document))).scalar() or 0
    ready_docs = (
        await session.execute(select(func.count()).where(Document.status == "ready"))
    ).scalar() or 0
    error_docs = (
        await session.execute(select(func.count()).where(Document.status == "error"))
    ).scalar() or 0
    pending_jobs = (
        await session.execute(select(func.count()).where(ProcessingJob.status == "pending"))
    ).scalar() or 0

    return {
        "status": "healthy",
        "queues": {
            "ingest": {"pending": pending_jobs, "processing": 0},
            "embed": {"pending": 0, "processing": 0},
        },
        "stats": {
            "documents_total": total_docs,
            "documents_ready": ready_docs,
            "documents_error": error_docs,
        },
    }


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List processing jobs with optional status filter.

    Args:
        status: Filter by job status (pending, processing, completed, error).
        limit: Maximum number of results.
        offset: Number of results to skip.
        session: Async database session.

    Returns:
        Paginated list of processing jobs.
    """
    query = select(ProcessingJob)
    if status:
        query = query.where(ProcessingJob.status == status)
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [ProcessingJobResponse.model_validate(j) for j in jobs],
        "total": len(jobs),
    }


@router.post("/retry/{job_id}", response_model=ProcessingJobResponse)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ProcessingJob:
    """Retry a failed processing job.

    Resets the job status to pending so it can be picked up by a worker.

    Args:
        job_id: UUID of the job to retry.
        session: Async database session.

    Returns:
        The updated job record.

    Raises:
        HTTPException: 404 if job not found.
    """
    result = await session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "pending"
    job.error = None
    await session.commit()
    await session.refresh(job)
    return job
