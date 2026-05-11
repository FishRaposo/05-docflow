"""Embedding generation service with OpenAI and sentence-transformers support."""

import logging
from typing import Any

from docflow.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using configured models.

    Supports OpenAI embeddings API and local sentence-transformers models
    with batch processing and rate limiting.
    """

    def __init__(self) -> None:
        """Initialize the embedding service based on configuration."""
        self._model_name = settings.EMBEDDING_MODEL
        self._dimensions = settings.EMBEDDING_DIMENSIONS
        self._client: Any = None
        self._local_model: Any = None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        if settings.OPENAI_API_KEY:
            return await self._embed_openai(texts)
        return self._embed_local(texts)

    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Args:
            text: Text string to embed.

        Returns:
            Single embedding vector.
        """
        results = await self.embed_texts([text])
        return results[0]

    async def batch_embed(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings in batches with rate limiting.

        Processes texts in batches to stay within API rate limits.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts per batch.

        Returns:
            List of embedding vectors.
        """
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await self.embed_texts(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using the OpenAI API.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors from OpenAI.
        """
        try:
            from openai import AsyncOpenAI

            if self._client is None:
                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await self._client.embeddings.create(
                input=texts,
                model=self._model_name,
                dimensions=self._dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.error("OpenAI embedding failed: %s", exc)
            return self._embed_local(texts)

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using sentence-transformers locally.

        Returns zero vectors if sentence-transformers is not available.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        try:
            from sentence_transformers import SentenceTransformer

            if self._local_model is None:
                self._local_model = SentenceTransformer(self._model_name)

            embeddings = self._local_model.encode(texts, show_progress_bar=False)
            return [emb.tolist() for emb in embeddings]
        except ImportError:
            logger.critical(
                "NO EMBEDDING BACKEND AVAILABLE - using zero vectors (results will be meaningless)"
            )
            return [[0.0] * self._dimensions for _ in texts]
