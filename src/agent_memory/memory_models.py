from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROFILE = "profile"


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    namespace: str = "default"
    memory_type: MemoryType = MemoryType.SEMANTIC
    title: str = "Untitled"
    content: str = ""
    summary: str = ""
    source_type: str = "text"
    source_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance_score: float = 0.0
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    status: str = "active"


class MemorySearchResult(BaseModel):
    id: str
    title: str
    content: str
    score: float
    namespace: str
    memory_type: MemoryType
    source_type: str | None = None
