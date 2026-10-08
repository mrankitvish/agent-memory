"""RAG Engine — orchestrates chunking, embedding, storage, and retrieval."""

from datetime import datetime, timezone
from functools import wraps
import re
from threading import RLock

from agent_memory.memory_models import MemoryType

from agent_memory.engine.chunker import Chunker
from agent_memory.engine.embedder import Embedder
from agent_memory.engine.metadata_store import MetadataStore
from agent_memory.engine.vector_store import VectorStore
from agent_memory.log import get_logger
from agent_memory.models import (
    Document, DocumentStatus, IngestionResult,
    SearchResult, SourceType,
)

logger = get_logger(__name__)


def synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapped


class RAGEngine:
    """Core orchestrator: ingest content → chunk → embed → store → retrieve."""

    def __init__(self) -> None:
        self.lock = RLock()
        logger.info("Initializing RAG engine...")
        self.chunker = Chunker()
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self.metadata_store = MetadataStore()
        logger.info("RAG engine ready")

    @synchronized
    def ingest(
        self,
        text: str,
        source_type: SourceType | str,
        title: str = "Untitled",
        namespace: str = "default",
        source_url: str | None = None,
        filename: str | None = None,
        tags: list[str] | None = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        memory_id: str | None = None,
    ) -> IngestionResult:
        """Ingest text content into the knowledge base.

        Args:
            text: Raw text content to ingest.
            source_type: Origin type (text).
            title: Human-readable document title.
            namespace: Namespace for isolation.
            source_url: Original source URL if applicable.
            filename: Original filename if applicable.
            tags: Optional tags for categorization.

        Returns:
            IngestionResult with document_id and chunk_count.
        """
        if isinstance(source_type, str):
            source_type = SourceType(source_type)
        if not text.strip() or len(text) > 100_000:
            raise ValueError("Memory text must contain 1 to 100,000 characters.")
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_-]{0,58}[A-Za-z0-9])?", namespace):
            raise ValueError("Namespace must be 1-60 letters, digits, hyphens or underscores, with alphanumeric ends.")
        previous = self.get_document(memory_id) if memory_id else None
        if memory_id and previous is None:
            raise ValueError("Memory not found.")
        if previous and previous.namespace != namespace:
            raise ValueError("The namespace of an existing memory cannot be changed.")
        previous_chunks = self.metadata_store.get_chunks_by_document(previous.id) if previous else []

        # Create document record
        doc = Document(
            namespace=namespace,
            source_type=source_type,
            source_url=source_url,
            title=title,
            content=text,
            memory_type=memory_type,
            filename=filename,
            tags=tags or [],
            status=DocumentStatus.PROCESSING,
        )
        if previous:
            doc.id = previous.id
            doc.created_at = previous.created_at
        else:
            self.metadata_store.save_document(doc)
        logger.info("Ingestion started", document_id=doc.id, title=title)

        chunk_ids = []
        try:
            # Chunk
            chunks = self.chunker.chunk(text, document_id=doc.id)
            if not chunks:
                self.metadata_store.update_document_status(
                    doc.id, DocumentStatus.INDEXED, chunk_count=0,
                )
                return IngestionResult(
                    document_id=doc.id, title=title,
                    chunk_count=0, namespace=namespace,
                    message="Document was empty, no chunks created.",
                )

            # Embed
            chunk_texts = [c.text for c in chunks]
            embeddings = self.embedder.embed_texts(chunk_texts)

            # Store vectors in ChromaDB
            chunk_ids = [c.id for c in chunks]
            metadatas = [
                {
                    "document_id": doc.id,
                    "document_title": title,
                    "source_type": source_type.value,
                    "source_url": source_url or "",
                    "chunk_index": c.chunk_index,
                    "namespace": namespace,
                }
                for c in chunks
            ]
            self.vector_store.upsert(
                namespace=namespace,
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=metadatas,
            )

            doc.status = DocumentStatus.INDEXED
            doc.chunk_count = len(chunks)
            doc.updated_at = datetime.now(timezone.utc)
            self.metadata_store.replace_memory(doc, chunks)

            logger.info(
                "Ingestion complete",
                document_id=doc.id, chunks=len(chunks),
            )
            if previous_chunks:
                try:
                    self.vector_store.delete(namespace, [chunk.id for chunk in previous_chunks])
                except Exception as cleanup_error:
                    logger.warning("Old vector cleanup failed", error=str(cleanup_error))
            return IngestionResult(
                document_id=doc.id, title=title,
                chunk_count=len(chunks), namespace=namespace,
            )

        except Exception as e:
            logger.error("Ingestion failed", document_id=doc.id, error=str(e))
            if chunk_ids:
                self.vector_store.delete(namespace, chunk_ids)
            if not previous:
                self.metadata_store.update_document_status(
                    doc.id, DocumentStatus.FAILED, error_message=str(e),
                )
            raise

    @synchronized
    def search(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Semantic search across the knowledge base.

        Args:
            query: Natural language search query.
            namespace: Namespace to search within.
            top_k: Maximum number of results.

        Returns:
            List of SearchResult sorted by relevance.
        """
        query_embedding = self.embedder.embed_query(query)

        results = self.vector_store.query(
            namespace=namespace,
            query_embedding=query_embedding,
            n_results=top_k,
        )

        search_results: list[SearchResult] = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            for i, doc_id in enumerate(ids):
                meta = metadatas[i]
                current_chunks = self.metadata_store.get_chunks_by_document(meta.get("document_id", ""))
                if doc_id not in {chunk.id for chunk in current_chunks}:
                    continue
                # ChromaDB returns distance; convert to similarity score
                score = 1.0 - distances[i]
                search_results.append(
                    SearchResult(
                        text=documents[i],
                        score=round(score, 4),
                        document_id=meta.get("document_id", ""),
                        document_title=meta.get("document_title", ""),
                        source_type=meta.get("source_type", "text"),
                        source_url=meta.get("source_url") or None,
                        chunk_index=meta.get("chunk_index", 0),
                        namespace=namespace,
                    )
                )

        logger.debug("Search complete", query=query[:50], results=len(search_results))
        return search_results

    @synchronized
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its vectors/metadata.

        Returns:
            True if the document was found and deleted.
        """
        doc = self.metadata_store.get_document(document_id)
        if not doc:
            return False

        # Get chunk IDs to delete from vector store
        chunks = self.metadata_store.get_chunks_by_document(document_id)
        if chunks:
            chunk_ids = [c.id for c in chunks]
            self.vector_store.delete(doc.namespace, chunk_ids)

        # Delete from metadata store
        self.metadata_store.delete_document(document_id)
        logger.info("Document deleted", document_id=document_id)
        return True

    @synchronized
    def list_documents(
        self, namespace: str | None = None,
        source_type: str | None = None, limit: int = 100,
    ) -> list[Document]:
        """List documents with optional filtering."""
        return self.metadata_store.list_documents(namespace, source_type, limit)

    @synchronized
    def get_document(self, document_id: str) -> Document | None:
        """Get a single document by ID."""
        return self.metadata_store.get_document(document_id)

    @synchronized
    def search_documents(self, **kwargs) -> list[Document]:
        """Search documents by metadata."""
        return self.metadata_store.search_documents(**kwargs)
