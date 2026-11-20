"""
sqlite_store.py: Persistent SQLite document repository for SETU-NETRA.

Why this file exists:
In enterprise and production settings, document intelligence cannot rely on ephemeral
in-memory state or loose JSON files dumped into temporary directories. This module
provides a persistent, ACID-compliant, embedded document database storing documents,
pages, reconstructed blocks, spatial bounding boxes, and packed embedding vectors.
"""

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

from setu_netra.core.contracts import DocumentPageRecord, StoredDocument

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Compute cryptographic SHA-256 hash of a file for content deduplication."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class SQLiteDocumentStore:
    """Embedded, persistent document store backed by SQLite with vector storage support."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Union[str, Path] = "output/setu_netra.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._last_skipped_embeddings: List[Dict[str, Any]] = []
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema, WAL mode, foreign keys, and indices."""
        with self._conn:
            # High-performance concurrent reading and writing
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA foreign_keys = ON;")

            # 1. Documents Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_type TEXT NOT NULL,
                    page_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PROCESSED',
                    metadata_json TEXT DEFAULT '{}',
                    workspace_id TEXT NOT NULL DEFAULT 'default'
                );
            """)

            # 2. Pages Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    page_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                );
            """)

            # 3. Document Blocks Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS document_blocks (
                    block_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    block_id INTEGER NOT NULL,
                    block_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    bbox_json TEXT NOT NULL,
                    source_detection_indices_json TEXT DEFAULT '[]',
                    embedding_blob BLOB,
                    embedding_dim INTEGER DEFAULT 0,
                    embedding_engine TEXT DEFAULT '',
                    primary_domain TEXT DEFAULT '',
                    concepts_json TEXT DEFAULT '[]',
                    workspace_id TEXT NOT NULL DEFAULT 'default'
                );
            """)

            # 4. Conversations Table (Version 1.0 Multi-Turn Sessions)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT DEFAULT 'default_user',
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    workspace_id TEXT NOT NULL DEFAULT 'default'
                );
            """)

            # 5. Messages Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    model_id TEXT,
                    worker_id TEXT,
                    epistemic_status TEXT,
                    citations_json TEXT DEFAULT '[]',
                    request_id TEXT,
                    metadata_json TEXT DEFAULT '{}'
                );
            """)

            # Defensive schema reconciliation: ensure workspace_id column exists if tables existed previously
            for tbl in ["documents", "document_blocks", "conversations"]:
                try:
                    cur = self._conn.execute(f"PRAGMA table_info({tbl});")
                    cols = [r[1] for r in cur.fetchall()]
                    if cols and "workspace_id" not in cols:
                        self._conn.execute(f"ALTER TABLE {tbl} ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default';")
                except Exception:
                    pass

            # Indices for rapid querying
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_workspace ON documents(workspace_id);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(doc_id, page_number);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_doc ON document_blocks(doc_id, page_number);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_workspace ON document_blocks(workspace_id);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, timestamp);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_type ON document_blocks(block_type);")

    def save_document(
        self,
        doc_id: str,
        file_path: Path,
        file_hash: str,
        file_type: str,
        page_count: int = 1,
        status: str = "PROCESSED",
        metadata: Optional[Dict[str, Any]] = None,
        workspace_id: str = "default",
    ) -> StoredDocument:
        """Insert or replace a document record in the store."""
        path_obj = Path(file_path)
        meta_dict = metadata or {}
        now_iso = datetime.now(timezone.utc).isoformat()
        base_hash = file_hash.split(":")[0] if ":" in file_hash else file_hash
        effective_hash = base_hash if (workspace_id == "default" or ":" in file_hash) else f"{base_hash}:{workspace_id}"

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO documents (
                    doc_id, file_path, file_name, file_hash, file_type,
                    page_count, created_at, status, metadata_json, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    file_path = excluded.file_path,
                    file_name = excluded.file_name,
                    file_hash = excluded.file_hash,
                    file_type = excluded.file_type,
                    page_count = excluded.page_count,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    workspace_id = excluded.workspace_id;
                """,
                (
                    doc_id,
                    str(path_obj.resolve()),
                    path_obj.name,
                    effective_hash,
                    file_type,
                    page_count,
                    now_iso,
                    status,
                    json.dumps(meta_dict),
                    workspace_id,
                ),
            )

        return StoredDocument(
            doc_id=doc_id,
            file_path=path_obj,
            file_name=path_obj.name,
            file_hash=base_hash,
            page_count=page_count,
            created_at=now_iso,
            status=status,
            metadata=meta_dict,
            workspace_id=workspace_id,
        )

    def get_document_by_id(self, doc_id: str, workspace_id: Optional[str] = None) -> Optional[StoredDocument]:
        """Retrieve a stored document by its unique identifier, optionally filtered by workspace."""
        query = (
            "SELECT doc_id, file_path, file_name, file_hash, page_count, created_at, status, metadata_json, workspace_id "
            "FROM documents WHERE doc_id = ?"
        )
        params: List[Any] = [doc_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        query += ";"

        cursor = self._conn.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None
        keys = row.keys() if hasattr(row, "keys") else []
        ws_id = row["workspace_id"] if "workspace_id" in keys else "default"
        stored_hash = row["file_hash"]
        clean_hash = stored_hash.split(":")[0] if ":" in stored_hash else stored_hash
        return StoredDocument(
            doc_id=row["doc_id"],
            file_path=Path(row["file_path"]),
            file_name=row["file_name"],
            file_hash=clean_hash,
            page_count=row["page_count"],
            created_at=row["created_at"],
            status=row["status"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            workspace_id=ws_id,
        )

    def get_document_by_hash(self, file_hash: str, workspace_id: Optional[str] = None) -> Optional[StoredDocument]:
        """Check if a file with the given SHA-256 hash already exists in the store (deduplication)."""
        base_hash = file_hash.split(":")[0] if ":" in file_hash else file_hash
        scoped_hash = f"{base_hash}:{workspace_id}" if workspace_id else None

        if workspace_id:
            query = (
                "SELECT doc_id, file_path, file_name, file_hash, page_count, created_at, status, metadata_json, workspace_id "
                "FROM documents WHERE (file_hash = ? OR file_hash = ?) AND workspace_id = ?;"
            )
            params = [base_hash, scoped_hash, workspace_id]
        else:
            query = (
                "SELECT doc_id, file_path, file_name, file_hash, page_count, created_at, status, metadata_json, workspace_id "
                "FROM documents WHERE file_hash = ? OR file_hash LIKE ?;"
            )
            params = [base_hash, f"{base_hash}:%"]

        cursor = self._conn.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None
        keys = row.keys() if hasattr(row, "keys") else []
        ws_id = row["workspace_id"] if "workspace_id" in keys else "default"
        stored_hash = row["file_hash"]
        clean_hash = stored_hash.split(":")[0] if ":" in stored_hash else stored_hash
        return StoredDocument(
            doc_id=row["doc_id"],
            file_path=Path(row["file_path"]),
            file_name=row["file_name"],
            file_hash=clean_hash,
            page_count=row["page_count"],
            created_at=row["created_at"],
            status=row["status"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            workspace_id=ws_id,
        )

    def list_documents(self, workspace_id: Optional[str] = None) -> List[StoredDocument]:
        """List stored documents ordered by creation timestamp, optionally filtered by workspace."""
        query = (
            "SELECT doc_id, file_path, file_name, file_hash, page_count, created_at, status, metadata_json, workspace_id "
            "FROM documents "
        )
        params: List[Any] = []
        if workspace_id:
            query += "WHERE workspace_id = ? "
            params.append(workspace_id)
        query += "ORDER BY created_at DESC;"

        cursor = self._conn.execute(query, tuple(params))
        results: List[StoredDocument] = []
        for row in cursor.fetchall():
            keys = row.keys() if hasattr(row, "keys") else []
            ws_id = row["workspace_id"] if "workspace_id" in keys else "default"
            stored_hash = row["file_hash"]
            clean_hash = stored_hash.split(":")[0] if ":" in stored_hash else stored_hash
            results.append(
                StoredDocument(
                    doc_id=row["doc_id"],
                    file_path=Path(row["file_path"]),
                    file_name=row["file_name"],
                    file_hash=clean_hash,
                    page_count=row["page_count"],
                    created_at=row["created_at"],
                    status=row["status"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                    workspace_id=ws_id,
                )
            )
        return results

    get_all_documents = list_documents

    def delete_document(self, doc_id: str, workspace_id: Optional[str] = None) -> bool:
        """Delete a document and all its associated pages and blocks (CASCADE), scoped to workspace if provided."""
        with self._conn:
            if workspace_id:
                check = self._conn.execute(
                    "SELECT 1 FROM documents WHERE doc_id = ? AND workspace_id = ?;",
                    (doc_id, workspace_id),
                )
                if not check.fetchone():
                    return False
            self._conn.execute("DELETE FROM document_blocks WHERE doc_id = ?;", (doc_id,))
            self._conn.execute("DELETE FROM pages WHERE doc_id = ?;", (doc_id,))
            cursor = self._conn.execute("DELETE FROM documents WHERE doc_id = ?;", (doc_id,))
            return cursor.rowcount > 0

    def clear_document_blocks(self, doc_id: str) -> None:
        """Clear all blocks and pages for a document to prepare for clean re-indexing."""
        with self._conn:
            self._conn.execute("DELETE FROM document_blocks WHERE doc_id = ?;", (doc_id,))
            self._conn.execute("DELETE FROM pages WHERE doc_id = ?;", (doc_id,))

    # -------------------------------------------------------------------------
    # Version 1.0 Multi-Turn Conversation Persistence
    # -------------------------------------------------------------------------

    def create_conversation(
        self,
        title: str,
        user_id: str = "default_user",
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        workspace_id: str = "default",
    ) -> str:
        """Create a new persistent conversation session."""
        c_id = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        now = time.time()
        meta_json = json.dumps(metadata or {}, default=str)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at, metadata_json, workspace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (c_id, user_id, title.strip() or "New Conversation", now, now, meta_json, workspace_id),
            )
        return c_id

    def list_conversations(
        self,
        user_id: Optional[str] = "default_user",
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all conversation sessions ordered by most recently updated, optionally filtered by workspace."""
        query = (
            "SELECT conversation_id, user_id, title, created_at, updated_at, metadata_json, workspace_id "
            "FROM conversations "
        )
        conditions: List[str] = []
        params: List[Any] = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if workspace_id is not None:
            conditions.append("workspace_id = ?")
            params.append(workspace_id)
        if conditions:
            query += "WHERE " + " AND ".join(conditions) + " "
        query += "ORDER BY updated_at DESC;"

        cursor = self._conn.execute(query, tuple(params))
        conversations: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            keys = row.keys() if hasattr(row, "keys") else []
            ws_id = row["workspace_id"] if "workspace_id" in keys else "default"
            conversations.append({
                "conversation_id": row["conversation_id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "workspace_id": ws_id,
            })
        return conversations

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve details of a single conversation session."""
        cursor = self._conn.execute(
            """
            SELECT conversation_id, user_id, title, created_at, updated_at, metadata_json
            FROM conversations
            WHERE conversation_id = ?;
            """,
            (conversation_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "conversation_id": row["conversation_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation session and all its messages (CASCADE)."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM conversations WHERE conversation_id = ?;", (conversation_id,))
            return cursor.rowcount > 0

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        epistemic_status: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """Append a message to a conversation session and update the conversation timestamp."""
        m_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        now = time.time()
        cites_json = json.dumps(citations or [], default=str)
        meta_json = json.dumps(metadata or {}, default=str)

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO messages (
                    message_id, conversation_id, role, content, timestamp,
                    model_id, worker_id, epistemic_status, citations_json, request_id, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    m_id, conversation_id, role, content, now,
                    model_id, worker_id, epistemic_status, cites_json, request_id, meta_json
                ),
            )
            # Update conversation updated_at
            self._conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?;",
                (now, conversation_id),
            )
        return m_id

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve chronological messages for a conversation session."""
        cursor = self._conn.execute(
            """
            SELECT message_id, conversation_id, role, content, timestamp,
                   model_id, worker_id, epistemic_status, citations_json, request_id, metadata_json
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ?;
            """,
            (conversation_id, limit),
        )
        messages: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            messages.append({
                "message_id": row["message_id"],
                "conversation_id": row["conversation_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "model_id": row["model_id"],
                "worker_id": row["worker_id"],
                "epistemic_status": row["epistemic_status"],
                "citations": json.loads(row["citations_json"] or "[]"),
                "request_id": row["request_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            })
        return messages

    def save_page(
        self,
        page_id: str,
        doc_id: str,
        page_number: int,
        width: int,
        height: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or replace a page record."""
        meta_dict = metadata or {}
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO pages (page_id, doc_id, page_number, width, height, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                    width = excluded.width,
                    height = excluded.height,
                    metadata_json = excluded.metadata_json;
                """,
                (page_id, doc_id, page_number, width, height, json.dumps(meta_dict)),
            )

    def get_pages(self, doc_id: str) -> List[DocumentPageRecord]:
        """Retrieve all pages for a document ordered by page number."""
        cursor = self._conn.execute(
            "SELECT page_id, doc_id, page_number, width, height, metadata_json "
            "FROM pages WHERE doc_id = ? ORDER BY page_number ASC;",
            (doc_id,),
        )
        return [
            DocumentPageRecord(
                page_id=row["page_id"],
                doc_id=row["doc_id"],
                page_number=row["page_number"],
                width=row["width"],
                height=row["height"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in cursor.fetchall()
        ]

    def get_page(self, doc_id: str, page_number: int) -> Optional[DocumentPageRecord]:
        """Retrieve a specific page record by doc_id and page_number."""
        cursor = self._conn.execute(
            "SELECT page_id, doc_id, page_number, width, height, metadata_json "
            "FROM pages WHERE doc_id = ? AND page_number = ? LIMIT 1;",
            (doc_id, page_number),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return DocumentPageRecord(
            page_id=row["page_id"],
            doc_id=row["doc_id"],
            page_number=row["page_number"],
            width=row["width"],
            height=row["height"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def save_blocks(
        self,
        doc_id: str,
        page_number: int,
        blocks_data: Sequence[Dict[str, Any]],
        workspace_id: str = "default",
    ) -> int:
        """Bulk insert document blocks and their embedding vectors."""
        if not blocks_data:
            return 0

        # Remove existing blocks for this document and page before refreshing
        with self._conn:
            self._conn.execute(
                "DELETE FROM document_blocks WHERE doc_id = ? AND page_number = ?;",
                (doc_id, page_number),
            )

            rows_to_insert = []
            for b in blocks_data:
                vec = b.get("embedding")
                embedding_blob = None
                embedding_dim = 0
                if vec is not None:
                    vec_arr = np.asarray(vec, dtype=np.float32)
                    embedding_blob = vec_arr.tobytes()
                    embedding_dim = len(vec_arr)

                bbox = b.get("bounding_box", (0.0, 0.0, 0.0, 0.0))
                rows_to_insert.append((
                    doc_id,
                    page_number,
                    int(b.get("block_id", 0)),
                    str(b.get("block_type", "PARAGRAPH")),
                    str(b.get("text", "")),
                    float(b.get("confidence", 1.0)),
                    json.dumps(list(bbox)),
                    json.dumps(list(b.get("source_detection_indices", []))),
                    embedding_blob,
                    embedding_dim,
                    str(b.get("embedding_engine", "")),
                    str(b.get("primary_domain", "")),
                    json.dumps(list(b.get("concepts", []))),
                    workspace_id,
                ))

            self._conn.executemany(
                """
                INSERT INTO document_blocks (
                    doc_id, page_number, block_id, block_type, text, confidence,
                    bbox_json, source_detection_indices_json, embedding_blob,
                    embedding_dim, embedding_engine, primary_domain, concepts_json,
                    workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows_to_insert,
            )

        return len(rows_to_insert)

    def get_blocks(
        self,
        doc_id: Optional[str] = None,
        page_number: Optional[int] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored blocks filtered by doc_id, page_number, and/or workspace_id."""
        query = (
            "SELECT b.doc_id, d.file_name, b.page_number, b.block_id, b.block_type, "
            "b.text, b.confidence, b.bbox_json, b.source_detection_indices_json, "
            "b.embedding_dim, b.embedding_engine, b.primary_domain, b.concepts_json "
            "FROM document_blocks b "
            "JOIN documents d ON b.doc_id = d.doc_id "
        )
        params: List[Any] = []
        conditions: List[str] = []

        if doc_id:
            conditions.append("b.doc_id = ?")
            params.append(doc_id)
        if page_number is not None:
            conditions.append("b.page_number = ?")
            params.append(page_number)
        if workspace_id:
            conditions.append("(d.workspace_id = ? OR b.workspace_id = ?)")
            params.append(workspace_id)
            params.append(workspace_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY b.doc_id, b.page_number, b.block_id ASC;"

        cursor = self._conn.execute(query, tuple(params))
        results = []
        for row in cursor.fetchall():
            results.append({
                "doc_id": row["doc_id"],
                "document_name": row["file_name"],
                "page_number": row["page_number"],
                "block_id": row["block_id"],
                "block_type": row["block_type"],
                "text": row["text"],
                "confidence": row["confidence"],
                "bounding_box": tuple(json.loads(row["bbox_json"])),
                "source_detection_indices": json.loads(row["source_detection_indices_json"]),
                "embedding_dim": row["embedding_dim"],
                "embedding_engine": row["embedding_engine"],
                "primary_domain": row["primary_domain"],
                "concepts": json.loads(row["concepts_json"]),
            })
        return results

    def _record_skipped_embedding(
        self,
        doc_id: str,
        page_number: int,
        block_id: int,
        reason: str,
        blob_len: int,
        stored_dim: Optional[int],
    ) -> None:
        """Record diagnostic information for an invalid or skipped embedding."""
        self._last_skipped_embeddings.append({
            "doc_id": doc_id,
            "page_number": page_number,
            "block_id": block_id,
            "reason": reason,
            "blob_length_bytes": blob_len,
            "stored_dim": stored_dim,
        })

    def get_last_skipped_embeddings(self) -> List[Dict[str, Any]]:
        """Return diagnostic records of any invalid embeddings skipped during the last call to get_all_embeddings."""
        return list(self._last_skipped_embeddings)

    def get_all_embeddings(
        self,
        engine_name: Optional[str] = None,
        expected_dim: Optional[int] = None,
        doc_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """Retrieve all blocks with non-empty embeddings and unpack into an (N, D) numpy array.

        Defensive validation policy:
        1. Checks that embedding BLOB is non-empty.
        2. Validates byte-alignment (len(blob) % 4 == 0) for float32 IEEE 754 buffers.
        3. Catches and logs any deserialization exceptions without crashing.
        4. Validates that unpacked float count strictly matches stored metadata dimension.
        5. Validates dimension consistency across stacked matrix rows.
        6. Rejects vectors containing NaN, positive infinity, or negative infinity.
        7. Invalid blocks are defensively skipped and recorded in diagnostic logs;
           they are never replaced with fabricated or zero vectors.

        Args:
            engine_name: Optional filter for embedding engine (e.g. 'all-minilm-l6-v2').
            expected_dim: Optional expected vector dimension (e.g. 384 or 512).
            doc_id: Optional document ID filter.
            workspace_id: Optional workspace ID filter.

        Returns:
            Tuple of (block_metadata_list, embedding_matrix).
        """
        query = (
            "SELECT b.doc_id, d.file_name, b.page_number, b.block_id, b.block_type, "
            "b.text, b.confidence, b.bbox_json, b.embedding_blob, b.embedding_dim, "
            "b.embedding_engine, b.primary_domain "
            "FROM document_blocks b "
            "JOIN documents d ON b.doc_id = d.doc_id "
            "WHERE b.embedding_blob IS NOT NULL "
        )
        params: List[Any] = []
        if doc_id:
            query += "AND b.doc_id = ? "
            params.append(doc_id)
        if engine_name:
            query += "AND b.embedding_engine = ? "
            params.append(engine_name)
        if workspace_id:
            query += "AND (d.workspace_id = ? OR b.workspace_id = ?) "
            params.extend([workspace_id, workspace_id])

        query += "ORDER BY b.doc_id, b.page_number, b.block_id ASC;"

        cursor = self._conn.execute(query, tuple(params))
        self._last_skipped_embeddings = []
        metadata_list: List[Dict[str, Any]] = []
        vector_list: List[np.ndarray] = []
        target_dim: Optional[int] = expected_dim

        for row in cursor.fetchall():
            doc_id = row["doc_id"]
            page_num = row["page_number"]
            block_id = row["block_id"]
            blob = row["embedding_blob"]
            stored_dim = row["embedding_dim"]

            # 1. Check for empty or None BLOB
            if not blob or len(blob) == 0:
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, "empty_blob", 0, stored_dim
                )
                continue

            # 2. Check for byte alignment (float32 requires multiple of 4 bytes)
            if len(blob) % 4 != 0:
                reason = f"malformed_blob_length: byte length {len(blob)} is not a multiple of 4"
                logger.warning(
                    "Skipping malformed embedding for Doc %s, Page %d, Block %d: %s",
                    doc_id, page_num, block_id, reason
                )
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, reason, len(blob), stored_dim
                )
                continue

            # 3. Safe deserialization
            try:
                arr = np.frombuffer(blob, dtype=np.float32)
            except Exception as e:
                reason = f"deserialization_exception: {e}"
                logger.warning(
                    "Error deserializing embedding for Doc %s, Page %d, Block %d: %s",
                    doc_id, page_num, block_id, reason
                )
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, reason, len(blob), stored_dim
                )
                continue

            # 4. Check for dimension match with stored metadata
            num_floats = len(arr)
            if stored_dim is not None and stored_dim > 0 and num_floats != stored_dim:
                reason = f"dimension_mismatch: metadata indicates {stored_dim} dims, but blob has {num_floats}"
                logger.warning(
                    "Embedding dimension mismatch for Doc %s, Page %d, Block %d: %s",
                    doc_id, page_num, block_id, reason
                )
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, reason, len(blob), stored_dim
                )
                continue

            # 5. Check for dimension consistency across the stacked matrix
            if target_dim is None:
                target_dim = num_floats
            elif num_floats != target_dim:
                reason = f"inconsistent_matrix_dimension: expected {target_dim} dims, got {num_floats}"
                logger.warning(
                    "Inconsistent embedding dimension for Doc %s, Page %d, Block %d: %s",
                    doc_id, page_num, block_id, reason
                )
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, reason, len(blob), stored_dim
                )
                continue

            # 6. Check for NaN or infinite values
            if not np.all(np.isfinite(arr)):
                has_nan = bool(np.isnan(arr).any())
                has_inf = bool(np.isinf(arr).any())
                reason = f"non_finite_values: nan={has_nan}, inf={has_inf}"
                logger.warning(
                    "Embedding contains NaN or Inf for Doc %s, Page %d, Block %d: %s",
                    doc_id, page_num, block_id, reason
                )
                self._record_skipped_embedding(
                    doc_id, page_num, block_id, reason, len(blob), stored_dim
                )
                continue

            # Valid embedding
            vector_list.append(arr)
            metadata_list.append({
                "doc_id": row["doc_id"],
                "document_name": row["file_name"],
                "page_number": row["page_number"],
                "block_id": row["block_id"],
                "block_type": row["block_type"],
                "text": row["text"],
                "confidence": row["confidence"],
                "bounding_box": tuple(json.loads(row["bbox_json"])),
                "embedding_dim": num_floats,
                "embedding_engine": row["embedding_engine"],
                "primary_domain": row["primary_domain"],
            })

        if not vector_list:
            return [], np.empty((0, 0), dtype=np.float32)

        matrix = np.vstack(vector_list)
        return metadata_list, matrix

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()

    def __enter__(self) -> "SQLiteDocumentStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
