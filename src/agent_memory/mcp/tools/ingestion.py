"""MCP text memory ingestion."""

from agent_memory.engine.rag_engine import RAGEngine
from agent_memory.models import SourceType
from agent_memory.memory_models import MemoryType
from typing import Annotated
from pydantic import Field


def register_ingestion_tools(mcp, engine: RAGEngine):
    """Register all ingestion tools on the MCP server."""

    @mcp.tool(
        description=(
            "Store text content in the knowledge base for later retrieval. "
            "Use this when the user wants to remember information, save notes, "
            "or add knowledge from pasted text."
        )
    )
    def save_memory(
        text: Annotated[str, Field(min_length=1, max_length=100_000)],
        title: Annotated[str, Field(min_length=1, max_length=200)] = "Untitled",
        namespace: str = "default",
        tags: list[str] | None = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
    ) -> dict:
        """Save a new text memory; use update_memory to change an existing memory."""
        result = engine.ingest(
            text=text,
            source_type=SourceType.TEXT,
            title=title,
            namespace=namespace,
            tags=tags,
            memory_type=memory_type,
        )
        response = result.model_dump()
        response["memory_id"] = response.pop("document_id")
        return response

