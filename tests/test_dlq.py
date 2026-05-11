"""Tests for the dead letter queue (DLQ)."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from docflow.queue.dlq import DeadLetterQueue


class TestDeadLetterQueue:
    """Tests for the dead letter queue operations."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    async def dlq(self, mock_redis: AsyncMock) -> DeadLetterQueue:
        with patch("docflow.queue.dlq.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            dlq = DeadLetterQueue()
            await dlq.connect()
            return dlq

    @pytest.mark.asyncio
    async def test_dlq_push(self, dlq: DeadLetterQueue, mock_redis: AsyncMock) -> None:
        job = {"document_id": str(uuid4()), "source": "local"}
        error = "Connection timeout"

        await dlq.push(job, error)

        mock_redis.hset.assert_called_once()
        args = mock_redis.hset.call_args[0]
        assert args[0] == dlq.DLQ_KEY

    @pytest.mark.asyncio
    async def test_dlq_list(self, dlq: DeadLetterQueue, mock_redis: AsyncMock) -> None:
        mock_redis.hgetall = AsyncMock(return_value={
            "doc-1": '{"job": {"document_id": "abc"}, "error": "timeout", "timestamp": "", "retry_count": 0}'
        })

        entries = await dlq.list_entries()
        assert isinstance(entries, list)
        assert len(entries) == 1
        mock_redis.hgetall.assert_called_once_with(dlq.DLQ_KEY)

    @pytest.mark.asyncio
    async def test_dlq_retry(self, dlq: DeadLetterQueue, mock_redis: AsyncMock) -> None:
        doc_id = str(uuid4())
        entry = {
            "job": {"document_id": doc_id},
            "error": "timeout",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "retry_count": 0,
        }

        mock_redis.hget = AsyncMock(return_value=json.dumps(entry))
        mock_redis.rpush = AsyncMock()
        mock_redis.hdel = AsyncMock()

        result = await dlq.retry(doc_id)
        assert result is not None
        assert result["document_id"] == doc_id
        mock_redis.hget.assert_called_once_with(dlq.DLQ_KEY, doc_id)
        mock_redis.rpush.assert_called_once()
        mock_redis.hdel.assert_called_once_with(dlq.DLQ_KEY, doc_id)

    @pytest.mark.asyncio
    async def test_dlq_retry_not_found(self, dlq: DeadLetterQueue, mock_redis: AsyncMock) -> None:
        mock_redis.hget = AsyncMock(return_value=None)

        result = await dlq.retry("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_dlq_clear(self, dlq: DeadLetterQueue, mock_redis: AsyncMock) -> None:
        mock_redis.hlen = AsyncMock(return_value=5)
        mock_redis.delete = AsyncMock()

        count = await dlq.clear()
        assert count == 5
        mock_redis.delete.assert_called_once_with(dlq.DLQ_KEY)

    @pytest.mark.asyncio
    async def test_dlq_push_preserves_job_data(
        self, dlq: DeadLetterQueue, mock_redis: AsyncMock
    ) -> None:
        doc_id = str(uuid4())
        job = {"document_id": doc_id, "source": "api", "priority": "high"}
        error = "Worker crashed during chunking"

        await dlq.push(job, error)

        args = mock_redis.hset.call_args[0]
        stored = json.loads(args[2])
        assert stored["job"] == job
        assert stored["error"] == error
        assert "timestamp" in stored
        assert stored["retry_count"] == 0
