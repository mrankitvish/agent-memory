"""Text chunking with recursive character splitting."""

from agent_memory.config import settings
from agent_memory.log import get_logger
from agent_memory.models import Chunk

logger = get_logger(__name__)

# Sentence-ending separators tried in order; fallback to character split.
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


class Chunker:
    """Splits text into overlapping chunks using recursive character splitting.

    Tries to split on natural boundaries (paragraphs, sentences) before
    falling back to character-level splits.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        logger.info(
            "Chunker initialized",
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def chunk(self, text: str, document_id: str) -> list[Chunk]:
        """Split text into chunks with metadata.

        Args:
            text: Raw text to chunk.
            document_id: Parent document ID to link chunks to.

        Returns:
            List of Chunk objects with positional metadata.
        """
        if not text or not text.strip():
            return []

        raw_chunks = self._recursive_split(text, _SEPARATORS)

        chunks: list[Chunk] = []
        char_offset = 0

        for idx, chunk_text in enumerate(raw_chunks):
            # Find the actual position of this chunk in the original text
            start = text.find(chunk_text, char_offset)
            if start == -1:
                start = char_offset

            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_index=idx,
                    text=chunk_text,
                    char_start=start,
                    char_end=start + len(chunk_text),
                )
            )
            # Move offset forward, but allow overlap
            char_offset = start + len(chunk_text) - self.chunk_overlap

        logger.debug("Chunked text", chunk_count=len(chunks), text_length=len(text))
        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text trying each separator in order."""
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        if not separators:
            # Last resort: hard character split
            return self._hard_split(text)

        sep = separators[0]
        remaining_seps = separators[1:]

        if sep == "":
            return self._hard_split(text)

        parts = text.split(sep)
        result: list[str] = []
        current = ""

        for part in parts:
            candidate = f"{current}{sep}{part}" if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                # Flush current buffer
                if current:
                    result.append(current.strip())
                # If this single part is too large, recurse with finer separators
                if len(part) > self.chunk_size:
                    result.extend(self._recursive_split(part, remaining_seps))
                    current = ""
                else:
                    current = part

        if current and current.strip():
            result.append(current.strip())

        return [r for r in result if r]

    def _hard_split(self, text: str) -> list[str]:
        """Split text into fixed-size character chunks with overlap."""
        result: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                result.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return result
