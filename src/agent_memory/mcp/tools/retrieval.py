"""MCP semantic memory recall."""

from typing import Annotated
from pydantic import Field

from agent_memory.engine.rag_engine import RAGEngine


def register_retrieval_tools(mcp, engine: RAGEngine):
    """Register all retrieval tools on the MCP server."""

    @mcp.tool(
        description=(
            "Search the knowledge base using semantic similarity. "
            "Use this when the user asks a question that might be answered "
            "by previously stored knowledge. Returns the most relevant "
            "text chunks."
        )
    )
    def recall_memories(
        query: Annotated[str, Field(min_length=1, max_length=2000)],
        namespace: str = "default",
        top_k: Annotated[int, Field(ge=1, le=100)] = 5,
    ) -> list[dict]:
        """Semantic search across ingested knowledge."""
        results = engine.search(query, namespace=namespace, top_k=top_k)
        return [
            {
                "text": r.text,
                "memory_id": r.document_id,
                "score": r.score,
                "title": r.document_title,
                "namespace": r.namespace,
            }
            for r in results
        ]

    @mcp.tool(
        description=(
            "Recall semantically relevant memory chunks with memory IDs, titles, "
            "namespaces and chunk indexes for traceable answers. Scores are similarity, not truth."
        )
    )
    def recall_memories_with_sources(
        query: Annotated[str, Field(min_length=1, max_length=2000)],
        namespace: str = "default",
        top_k: Annotated[int, Field(ge=1, le=100)] = 5,
    ) -> list[dict]:
        """Semantic search with full citation metadata."""
        results = engine.search(query, namespace=namespace, top_k=top_k)
        return [{"memory_id": result.document_id, "title": result.document_title,
             "text": result.text, "score": result.score,
             "namespace": result.namespace, "chunk_index": result.chunk_index}
            for result in results]
