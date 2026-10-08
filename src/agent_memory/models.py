"""Core data models shared across the application."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field
from agent_memory.memory_models import MemoryType


def _make_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    """Supported content source types."""
    TEXT = "text"


class DocumentStatus(str, Enum):
    """Lifecycle status of an ingested document."""
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(BaseModel):
    """Metadata record for an ingested document."""
    id: str = Field(default_factory=_make_id)
    namespace: str = "default"
    source_type: SourceType
    source_url: str | None = None
    title: str = "Untitled"
    content: str = ""
    memory_type: MemoryType = MemoryType.SEMANTIC
    filename: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: DocumentStatus = DocumentStatus.PROCESSING
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    error_message: str | None = None


class Chunk(BaseModel):
    """A single chunk of text from a document."""
    id: str = Field(default_factory=_make_id)
    document_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int


class SearchResult(BaseModel):
    """A single result from a semantic search."""
    text: str
    score: float
    document_id: str
    document_title: str
    source_type: SourceType
    source_url: str | None = None
    chunk_index: int
    namespace: str


class IngestionResult(BaseModel):
    """Response returned after successful ingestion."""
    document_id: str
    title: str
    chunk_count: int
    namespace: str
    message: str = "Document indexed successfully."


class ErrorResponse(BaseModel):
    """Structured error returned by tools."""
    error: str
    error_code: str
    detail: str | None = None
