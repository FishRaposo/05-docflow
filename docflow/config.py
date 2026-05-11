"""Application configuration with environment variable loading."""

from typing_extensions import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via environment variables or a .env file.
    """

    DATABASE_URL: str = "postgresql+asyncpg://docflow:docflow@localhost:5432/docflow"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    CHUNKING_STRATEGY: str = "fixed"

    QUEUE_NAME: str = "docflow"
    WORKER_CONCURRENCY: int = 4

    STORAGE_BACKEND: str = "local"
    STORAGE_PATH: str = "./data/uploads"

    INGESTION_BATCH_SIZE: int = 10
    MAX_FILE_SIZE_MB: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_chunk_config(self) -> Self:
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.CHUNK_OVERLAP}) must be less than CHUNK_SIZE ({self.CHUNK_SIZE})"
            )
        return self


settings = Settings()
