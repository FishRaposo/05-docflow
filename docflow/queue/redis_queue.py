"""Redis-based job queue for async pipeline processing."""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from docflow.config import settings

logger = logging.getLogger(__name__)


class RedisQueue:
    """Async Redis queue for managing pipeline processing jobs.

    Provides enqueue/dequeue operations with connection management
    and retry logic.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        """Initialize the Redis queue.

        Args:
            redis_url: Redis connection URL. Defaults to configured URL.
        """
        self._redis_url = redis_url or settings.REDIS_URL
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Establish connection to Redis with retry logic.

        Retries connection up to 3 times with 1-second intervals.
        """
        for attempt in range(3):
            try:
                self._client = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._client.ping()
                logger.info("Connected to Redis at %s", self._redis_url)
                return
            except Exception as exc:
                logger.warning("Redis connection attempt %d failed: %s", attempt + 1, exc)
        raise ConnectionError(f"Failed to connect to Redis at {self._redis_url}")

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def enqueue(self, queue_name: str, payload: dict[str, Any]) -> None:
        """Add a job to the specified queue.

        Args:
            queue_name: Name of the queue.
            payload: Job data to enqueue (must be JSON-serializable).
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None
        await self._client.rpush(queue_name, json.dumps(payload))
        logger.debug("Enqueued job to %s: %s", queue_name, payload)

    async def dequeue(self, queue_name: str, timeout: int = 5) -> dict[str, Any] | None:
        """Remove and return a job from the specified queue.

        Blocks for up to timeout seconds waiting for a job.

        Args:
            queue_name: Name of the queue.
            timeout: Seconds to wait for a job (0 for non-blocking).

        Returns:
            Job payload dictionary, or None if no job is available.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None
        result = await self._client.blpop(queue_name, timeout=timeout)
        if result is None:
            return None
        _, data = result
        return json.loads(data)

    async def get_queue_length(self, queue_name: str) -> int:
        """Get the number of jobs waiting in a queue.

        Args:
            queue_name: Name of the queue.

        Returns:
            Number of pending jobs.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None
        return await self._client.llen(queue_name)

    async def clear_queue(self, queue_name: str) -> None:
        """Remove all jobs from a queue.

        Args:
            queue_name: Name of the queue to clear.
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None
        await self._client.delete(queue_name)
        logger.info("Cleared queue: %s", queue_name)
