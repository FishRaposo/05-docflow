"""SQLAlchemy 2.0 models and Pydantic schemas for DocFlow."""

import uuid
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from docflow.config import settings
from docflow.db import Base


class Source(Base):
    """A document source configuration (local directory, webhook, API)."""

    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """An ingested document with metadata and processing status."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("sources.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    """A text chunk from a document with optional embedding vector."""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingJob(Base):
    """A pipeline processing job with status tracking."""

    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceCreate(BaseModel):
    """Schema for creating a new source."""

    name: str = Field(description="Human-readable source name")
    type: str = Field(description="Source type: local, webhook, or api")
    config: dict[str, Any] | None = Field(default=None, description="Source-specific configuration")


class SourceResponse(BaseModel):
    """Schema for source API responses."""

    id: UUID
    name: str
    type: str
    config: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    """Schema for creating a new document record."""

    title: str = Field(description="Document title")
    file_path: str = Field(description="Path to stored file")
    file_type: str = Field(description="File extension")
    source_id: UUID | None = Field(default=None, description="Parent source ID")
    metadata_: dict[str, Any] | None = Field(default=None, description="Document metadata")


class DocumentResponse(BaseModel):
    """Schema for document API responses."""

    id: UUID
    source_id: UUID | None
    title: str
    file_path: str
    file_type: str
    content_hash: str | None
    fingerprint: str | None
    version: int
    status: str
    metadata_: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    """Schema for chunk API responses."""

    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata_: dict[str, Any] | None

    model_config = {"from_attributes": True}


class ProcessingJobResponse(BaseModel):
    """Schema for processing job API responses."""

    id: UUID
    document_id: UUID
    stage: str
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
