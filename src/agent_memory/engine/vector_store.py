"""ChromaDB vector store wrapper."""

import chromadb

from agent_memory.config import settings
from agent_memory.log import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Manages ChromaDB collections for namespace-isolated vector storage."""

    def __init__(self) -> None:
        chroma_path = str(settings.chroma_path)
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=chroma_path)
        logger.info("ChromaDB initialized", path=chroma_path)

    def _collection_name(self, namespace: str) -> str:
        """Map a namespace to a ChromaDB collection name."""
        # ChromaDB collection names: 3-63 chars, alphanumeric/underscores/hyphens
        safe = namespace.replace(" ", "_")[:63]
        return f"ns_{safe}" if safe else "ns_default"

    def get_or_create_collection(self, namespace: str) -> chromadb.Collection:
        """Get or create a collection for a namespace."""
        name = self._collection_name(namespace)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        namespace: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Insert or update vectors with metadata.

        Args:
            namespace: Target namespace/collection.
            ids: Unique IDs for each vector.
            embeddings: Embedding vectors.
            documents: Raw text for each vector (stored by ChromaDB).
            metadatas: Metadata dicts for each vector.
        """
        collection = self.get_or_create_collection(namespace)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted vectors", namespace=namespace, count=len(ids))

    def query(
        self,
        namespace: str,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Search for similar vectors.

        Args:
            namespace: Namespace/collection to search.
            query_embedding: Query vector.
            n_results: Number of results to return.
            where: Optional metadata filter.

        Returns:
            ChromaDB query result dict with ids, documents, metadatas, distances.
        """
        collection = self.get_or_create_collection(namespace)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        return collection.query(**kwargs)

    def delete(self, namespace: str, ids: list[str]) -> None:
        """Delete vectors by ID."""
        collection = self.get_or_create_collection(namespace)
        collection.delete(ids=ids)
        logger.debug("Deleted vectors", namespace=namespace, count=len(ids))

    def delete_collection(self, namespace: str) -> None:
        """Delete an entire namespace collection."""
        name = self._collection_name(namespace)
        try:
            self._client.delete_collection(name)
            logger.info("Deleted collection", namespace=namespace)
        except ValueError:
            logger.warning("Collection not found for deletion", namespace=namespace)

    def list_collections(self) -> list[str]:
        """List all namespace collection names."""
        collections = self._client.list_collections()
        return [c.name for c in collections]

    def count(self, namespace: str) -> int:
        """Count vectors in a namespace."""
        collection = self.get_or_create_collection(namespace)
        return collection.count()
