"""Pipeline monitoring and management API endpoints."""

from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.config import settings
from docflow.db import get_session
from docflow.db.models import Document, ProcessingJob, ProcessingJobResponse
from docflow.queue.dlq import DeadLetterQueue
from docflow.queue.redis_queue import RedisQueue

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

    queue = RedisQueue()
    await queue.connect()
    try:
        ingest_depth = await queue.get_queue_length(f"{settings.QUEUE_NAME}:ingest")
        embed_depth = await queue.get_queue_length(f"{settings.QUEUE_NAME}:embed")
    finally:
        await queue.disconnect()

    return {
        "status": "healthy",
        "queues": {
            "ingest": {"pending": ingest_depth, "processing": 0},
            "embed": {"pending": embed_depth, "processing": 0},
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


@router.get("/dlq")
async def list_dlq_entries(
    limit: int = 50,
) -> dict[str, Any]:
    """List entries in the Dead Letter Queue.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of DLQ entries with their metadata.
    """
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        dlq = DeadLetterQueue(redis_client)
        entries = await dlq.list_entries(limit)
        return {"entries": entries, "total": len(entries)}
    finally:
        await redis_client.aclose()


@router.post("/dlq/{dlq_id}/retry")
async def retry_dlq_entry(
    dlq_id: str,
) -> dict[str, Any]:
    """Retry a failed job from the Dead Letter Queue.

    Re-enqueues the job to its original queue and removes it from the DLQ.

    Args:
        dlq_id: UUID of the DLQ entry to retry.

    Returns:
        Confirmation of the retry action.

    Raises:
        HTTPException: 404 if the DLQ entry is not found.
    """
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        dlq = DeadLetterQueue(redis_client)
        success = await dlq.retry(dlq_id)
        if not success:
            raise HTTPException(status_code=404, detail="DLQ entry not found")
        return {"status": "retried", "dlq_id": dlq_id}
    finally:
        await redis_client.aclose()


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
