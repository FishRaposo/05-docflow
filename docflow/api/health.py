"""Health check API endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from docflow.__init__ import __version__
from docflow.db import get_session
from docflow.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Check API health and connectivity.

    Returns the API status, version, and connection states for dependencies.
    Performs real connectivity checks against the database and Redis.
    """
    db_status = "disconnected"
    redis_status = "disconnected"

    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)

    try:
        redis = RedisQueue()
        await redis.connect()
        redis_status = "connected"
        await redis.disconnect()
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)

    overall = "healthy" if db_status == "connected" else "degraded"

    return {
        "status": overall,
        "version": __version__,
        "database": db_status,
        "redis": redis_status,
    }
