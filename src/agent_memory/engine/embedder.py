"""Embedding generation using SentenceTransformers."""

from sentence_transformers import SentenceTransformer

from agent_memory.config import settings
from agent_memory.log import get_logger

logger = get_logger(__name__)

# Module-level singleton — initialized lazily on first use.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model (downloads on first use)."""
    global _model
    if _model is None:
        model_name = settings.embedding_model
        logger.info("Loading embedding model", model=model_name)
        _model = SentenceTransformer(model_name)
        logger.info(
            "Embedding model loaded",
            model=model_name,
            dimension=_model.get_embedding_dimension(),
        )
    return _model


class Embedder:
    """Generate embeddings for text chunks and queries."""

    def __init__(self) -> None:
        # Trigger model load on init so startup failures surface early.
        self._model = _get_model()
        self.dimension: int = self._model.get_embedding_dimension()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text chunks.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (list of floats).
        """
        if not texts:
            return []

        logger.debug("Embedding texts", count=len(texts))
        embeddings = self._model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query.

        Args:
            query: The search query string.

        Returns:
            Embedding vector as a list of floats.
        """
        embedding = self._model.encode(
            query,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embedding.tolist()
