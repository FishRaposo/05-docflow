"""Dead letter queue for failed processing jobs."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from docflow.config import settings

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Redis-based dead letter queue for failed pipeline jobs.

    Stores permanently failed jobs for inspection and retry.
    Each entry preserves the original payload along with failure
    metadata (error message, timestamp, retry count).

    Can be constructed with a Redis URL string or a Redis client instance.
    """

    DLQ_KEY = "docflow:dlq"

    def __init__(self, redis_url_or_client: str | aioredis.Redis | None = None) -> None:
        if isinstance(redis_url_or_client, str) or redis_url_or_client is None:
            self._redis_url = redis_url_or_client or settings.REDIS_URL
            self._client: aioredis.Redis | None = None
        else:
            self._redis_url = ""
            self._client = redis_url_or_client

    async def connect(self) -> None:
        for attempt in range(3):
            try:
                self._client = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._client.ping()
                logger.info("DLQ connected to Redis at %s", self._redis_url)
                return
            except Exception as exc:
                logger.warning("DLQ Redis connection attempt %d failed: %s", attempt + 1, exc)
        raise ConnectionError(f"Failed to connect DLQ to Redis at {self._redis_url}")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def push(self, job: dict[str, Any], error: str, _queue_name: str = "") -> str:
        """Push a failed job onto the dead letter queue.

        Args:
            job: Original job payload.
            error: Error message describing the failure.
            _queue_name: Ignored; kept for backward compatibility with caller interface.

        Returns:
            The DLQ entry ID.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None

        entry = {
            "job": job,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
        }
        entry_id = json.dumps(job.get("document_id", ""))
        await self._client.hset(self.DLQ_KEY, entry_id, json.dumps(entry))
        logger.info("Pushed job %s to DLQ: %s", entry_id, error)
        return entry_id

    async def list_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """List entries currently in the dead letter queue.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of DLQ entry dictionaries.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None

        raw = await self._client.hgetall(self.DLQ_KEY)
        entries = [json.loads(v) for v in raw.values()]
        return entries[:limit]

    async def retry(self, entry_id: str) -> dict[str, Any] | None:
        """Retry a failed job by moving it back to the ingest queue.

        Args:
            entry_id: The DLQ entry ID (document_id).

        Returns:
            The job payload if retried, None if not found.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None

        raw = await self._client.hget(self.DLQ_KEY, entry_id)
        if raw is None:
            logger.warning("DLQ retry failed: entry %s not found", entry_id)
            return None

        entry = json.loads(raw)
        entry["retry_count"] = entry.get("retry_count", 0) + 1

        ingest_queue = f"{settings.QUEUE_NAME}:ingest"
        await self._client.rpush(ingest_queue, json.dumps(entry["job"]))

        await self._client.hdel(self.DLQ_KEY, entry_id)
        logger.info("Retried DLQ entry %s to %s", entry_id, ingest_queue)
        return entry["job"]

    async def clear(self) -> int:
        """Remove all entries from the dead letter queue.

        Returns:
            Number of entries removed.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None

        count = await self._client.hlen(self.DLQ_KEY)
        await self._client.delete(self.DLQ_KEY)
        logger.info("Cleared DLQ: removed %d entries", count)
        return count
