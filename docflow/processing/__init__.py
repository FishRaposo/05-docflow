"""Document processing services for the ingestion pipeline."""

from docflow.processing.fingerprint import Fingerprinter
from docflow.processing.metadata import MetadataExtractor, DocumentMetadata
from docflow.processing.chunking import ChunkingService, ChunkCandidate
from docflow.processing.deduplication import DeduplicationService
from docflow.processing.embedding import EmbeddingService
from docflow.processing.versioning import VersioningService, DocumentVersion, VersionDiff

__all__ = [
    "Fingerprinter",
    "MetadataExtractor",
    "DocumentMetadata",
    "ChunkingService",
    "ChunkCandidate",
    "DeduplicationService",
    "EmbeddingService",
    "VersioningService",
    "DocumentVersion",
    "VersionDiff",
]
