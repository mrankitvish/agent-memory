"""SQLite metadata store for documents and chunks."""

import json
from datetime import datetime, timezone

import sqlite_utils

from agent_memory.config import settings
from agent_memory.log import get_logger
from agent_memory.models import Chunk, Document, DocumentStatus

logger = get_logger(__name__)


class MetadataStore:
    """SQLite-backed storage for document and chunk metadata."""

    def __init__(self) -> None:
        import sqlite3
        db_path = str(settings.metadata_db_path)
        settings.metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
        # Create connection with check_same_thread=False to support ASGI multi-threading
        conn = sqlite3.connect(db_path, check_same_thread=False)
        self._db = sqlite_utils.Database(conn)
        self._ensure_tables()
        logger.info("Metadata store initialized", path=db_path)

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        if "documents" not in self._db.table_names():
            self._db["documents"].create(
                {
                    "id": str, "namespace": str, "source_type": str,
                    "source_url": str, "title": str, "filename": str,
                    "tags": str, "status": str, "chunk_count": int,
                    "created_at": str, "updated_at": str, "error_message": str,
                },
                pk="id",
            )
        for column in ("content", "memory_type"):
            if column not in self._db["documents"].columns_dict:
                self._db["documents"].add_column(column, str)
        if "chunks" not in self._db.table_names():
            self._db["chunks"].create(
                {
                    "id": str, "document_id": str, "chunk_index": int,
                    "text": str, "char_start": int, "char_end": int,
                },
                pk="id",
                foreign_keys=[("document_id", "documents")],
            )

    def save_document(self, doc: Document) -> None:
        """Insert or update a document record."""
        self._db["documents"].upsert(
            {
                "id": doc.id, "namespace": doc.namespace,
                "source_type": doc.source_type.value,
                "source_url": doc.source_url or "",
                "title": doc.title, "filename": doc.filename or "",
                "content": doc.content, "memory_type": doc.memory_type.value,
                "tags": json.dumps(doc.tags), "status": doc.status.value,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat(),
                "error_message": doc.error_message or "",
            },
            pk="id",
        )

    def get_document(self, document_id: str) -> Document | None:
        """Retrieve a document by ID."""
        try:
            row = self._db["documents"].get(document_id)
        except sqlite_utils.db.NotFoundError:
            return None
        return self._row_to_document(row)

    def replace_memory(self, doc: Document, chunks: list[Chunk]) -> None:
        record = doc.model_dump(mode="json")
        record["tags"] = json.dumps(doc.tags)
        columns = list(record)
        placeholders = ", ".join("?" for column in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns)
        with self._db.conn:
            self._db.conn.execute(
                f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}", list(record.values()),
            )
            self._db.conn.execute("DELETE FROM chunks WHERE document_id = ?", [doc.id])
            self._db.conn.executemany(
                "INSERT INTO chunks (id, document_id, chunk_index, text, char_start, char_end) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(chunk.id, chunk.document_id, chunk.chunk_index, chunk.text,
                  chunk.char_start, chunk.char_end) for chunk in chunks],
            )

    def browse(self, namespace: str | None = None, memory_type: str | None = None,
               query: str = "", limit: int = 200, offset: int = 0) -> dict:
        clauses, params = ["1=1"], []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if memory_type:
            clauses.append("COALESCE(memory_type, 'semantic') = ?")
            params.append(memory_type)
        if query:
            clauses.append("(instr(lower(title), lower(?)) > 0 OR "
                           "instr(lower(COALESCE(content, '')), lower(?)) > 0 OR "
                           "instr(lower(tags), lower(?)) > 0)")
            params.extend([query, query, query])
        where = " AND ".join(clauses)
        total = self._db.execute(f"SELECT count(*) FROM documents WHERE {where}", params).fetchone()[0]
        rows = self._db.query(
            f"SELECT * FROM documents WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return {"items": [self._row_to_document(row) for row in rows], "total": total}

    def namespaces(self) -> list[str]:
        return [row[0] for row in self._db.execute(
            "SELECT DISTINCT namespace FROM documents ORDER BY namespace"
        ).fetchall()]

    def list_documents(
        self, namespace: str | None = None,
        source_type: str | None = None, limit: int = 100,
    ) -> list[Document]:
        """List documents with optional filtering."""
        clauses, params = [], []
        if namespace:
            clauses.append("namespace = ?"); params.append(namespace)
        if source_type:
            clauses.append("source_type = ?"); params.append(source_type)
        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._db.execute(sql, params).fetchall()
        cols = [d[0] for d in self._db.execute(sql, params).description]
        return [self._row_to_document(dict(zip(cols, r))) for r in rows]

    def update_document_status(
        self, document_id: str, status: DocumentStatus,
        chunk_count: int = 0, error_message: str | None = None,
    ) -> None:
        """Update document status after ingestion."""
        self._db["documents"].update(document_id, {
            "status": status.value, "chunk_count": chunk_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message or "",
        })

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks. Returns True if found."""
        if not self.get_document(document_id):
            return False
        self._db.execute("DELETE FROM chunks WHERE document_id = ?", [document_id])
        self._db["documents"].delete(document_id)
        return True

    def search_documents(
        self, query: str | None = None, tags: list[str] | None = None,
        source_type: str | None = None, namespace: str | None = None,
    ) -> list[Document]:
        """Search documents by metadata (title, tags, source_type)."""
        clauses, params = [], []
        if query:
            clauses.append("title LIKE ?"); params.append(f"%{query}%")
        if source_type:
            clauses.append("source_type = ?"); params.append(source_type)
        if namespace:
            clauses.append("namespace = ?"); params.append(namespace)
        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT 50"
        rows = self._db.execute(sql, params).fetchall()
        cols = [d[0] for d in self._db.execute(
            f"SELECT * FROM documents WHERE {where} LIMIT 0", params
        ).description]
        results = [self._row_to_document(dict(zip(cols, r))) for r in rows]
        if tags:
            results = [d for d in results if any(t in d.tags for t in tags)]
        return results

    def save_chunks(self, chunks: list[Chunk]) -> None:
        """Batch insert chunks."""
        self._db["chunks"].upsert_all(
            [{"id": c.id, "document_id": c.document_id,
              "chunk_index": c.chunk_index, "text": c.text,
              "char_start": c.char_start, "char_end": c.char_end}
             for c in chunks],
            pk="id",
        )

    def get_chunks_by_document(self, document_id: str) -> list[Chunk]:
        """Get all chunks for a document."""
        rows = list(self._db["chunks"].rows_where(
            "document_id = ?", [document_id], order_by="chunk_index",
        ))
        return [Chunk(**{k: row[k] for k in Chunk.model_fields}) for row in rows]

    @staticmethod
    def _row_to_document(row: dict) -> Document:
        """Convert a database row dict to a Document model."""
        tags_raw = row.get("tags", "[]")
        return Document(
            id=row["id"], namespace=row["namespace"],
            source_type=row["source_type"],
            source_url=row.get("source_url") or None,
            title=row["title"], filename=row.get("filename") or None,
            content=row.get("content") or "",
            memory_type=row.get("memory_type") or "semantic",
            tags=json.loads(tags_raw) if tags_raw else [],
            status=row["status"], chunk_count=row.get("chunk_count", 0),
            created_at=row["created_at"], updated_at=row["updated_at"],
            error_message=row.get("error_message") or None,
        )
