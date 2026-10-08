"""MCP memory browsing and lifecycle operations."""

from typing import Annotated

from pydantic import Field

from agent_memory.engine.rag_engine import RAGEngine
from agent_memory.memory_models import MemoryType
from agent_memory.models import Document, SourceType


def memory_record(doc: Document) -> dict:
    return {
        "memory_id": doc.id, "title": doc.title, "text": doc.content,
        "namespace": doc.namespace, "memory_type": doc.memory_type.value,
        "tags": doc.tags, "status": doc.status.value, "chunk_count": doc.chunk_count,
        "created_at": doc.created_at.isoformat(), "updated_at": doc.updated_at.isoformat(),
        "error_message": doc.error_message,
    }


def read_memory(engine: RAGEngine, memory_id: str) -> dict:
    with engine.lock:
        doc = engine.get_document(memory_id)
        if doc is None:
            raise ValueError("Memory not found.")
        return {**memory_record(doc), "chunks": [
            {"chunk_index": chunk.chunk_index, "text": chunk.text}
            for chunk in engine.metadata_store.get_chunks_by_document(memory_id)
        ]}


def register_management_tools(mcp, engine: RAGEngine):
    @mcp.tool(description="Browse saved memories by namespace and type, with pagination.",
              annotations={"readOnlyHint": True})
    def list_memories(
        namespace: str | None = None,
        memory_type: MemoryType | None = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        with engine.lock:
            result = engine.metadata_store.browse(namespace, memory_type, limit=limit, offset=offset)
            return {"items": [memory_record(doc) for doc in result["items"]], "total": result["total"]}

    @mcp.tool(description="Find memories by literal text in title, content or tags. For semantic recall use recall_memories.",
              annotations={"readOnlyHint": True})
    def search_memories(
        query: Annotated[str, Field(min_length=1, max_length=2000)],
        namespace: str | None = None,
        memory_type: MemoryType | None = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        with engine.lock:
            result = engine.metadata_store.browse(namespace, memory_type, query, limit, offset)
            return {"items": [memory_record(doc) for doc in result["items"]], "total": result["total"]}

    @mcp.tool(description="Read a memory by ID, including its full original text, metadata and indexed chunks.",
              annotations={"readOnlyHint": True})
    def get_memory(memory_id: str) -> dict:
        return read_memory(engine, memory_id)

    @mcp.tool(description="Update an existing memory without changing its ID or namespace. Omitted fields are retained; tags=[] clears tags. Rebuilds embeddings.",
              annotations={"destructiveHint": True})
    def update_memory(
        memory_id: str,
        text: Annotated[str | None, Field(min_length=1, max_length=100_000)] = None,
        title: Annotated[str | None, Field(min_length=1, max_length=200)] = None,
        tags: list[str] | None = None,
        memory_type: MemoryType | None = None,
    ) -> dict:
        with engine.lock:
            doc = engine.get_document(memory_id)
            if doc is None:
                raise ValueError("Memory not found.")
            if not doc.content and text is None:
                raise ValueError("Original text is unavailable; provide replacement text.")
            engine.ingest(
                text=text if text is not None else doc.content,
                source_type=SourceType.TEXT,
                title=title if title is not None else doc.title,
                namespace=doc.namespace,
                tags=tags if tags is not None else doc.tags,
                memory_type=memory_type if memory_type is not None else doc.memory_type,
                memory_id=memory_id,
            )
            return read_memory(engine, memory_id)

    @mcp.tool(description="Permanently delete a memory and its indexed chunks by ID. Only use when deletion is authorized.",
              annotations={"destructiveHint": True})
    def delete_memory(memory_id: str) -> dict:
        deleted = engine.delete_document(memory_id)
        return {"status": "deleted" if deleted else "not_found", "memory_id": memory_id}

    @mcp.tool(description="Check whether a memory is processing, indexed or failed.",
              annotations={"readOnlyHint": True})
    def get_memory_status(memory_id: str) -> dict:
        doc = engine.get_document(memory_id)
        if doc is None:
            return {"status": "not_found", "memory_id": memory_id}
        return {"memory_id": doc.id, "status": doc.status.value,
                "chunk_count": doc.chunk_count, "error_message": doc.error_message}
