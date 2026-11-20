# SETU-NETRA V2.0.0-RC1 — PHASE 2 DATABASE MIGRATION REPORT
**Reversible Schema Migrations, V1.1.0 Preservation & Concurrency Protocol**  
*Date: November 11, 2026*  
*Storage Engine: SQLite 3.50.4 with Write-Ahead Logging (WAL) Mode*  

---

## 1. Migration Architecture & Philosophy

In enterprise document intelligence systems, schema alterations cannot rely on ad-hoc scripts or recreation of database files (`DROP TABLE`). Data accumulated in production—such as ingested enterprise documents, OCR coordinates, layout reconstructions, and vector embeddings—is computationally expensive to regenerate.

The SETU-NETRA Phase 2 migration engine implemented in [`src/setu_netra/store/migrations.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/store/migrations.py) adheres to three non-negotiable principles:
1. **Non-Destructive Execution:** Pre-existing records are never deleted, overwritten, or modified during schema transitions.
2. **Deterministic Versioning:** Schema state is recorded in a dedicated `schema_migrations` ledger, guaranteeing that migrations are applied in strict sequential order exactly once.
3. **Reversibility (`up`/`down`):** Every forward migration provides an exact, symmetric rollback procedure capable of reverting the database schema to any previous version without corrupting underlying data.

---

## 2. Pre-Migration Backup Protocol

Before any migration or rollback operation executes, the runner invokes `backup_database()`.

```python
def backup_database(db_path: Path | str, backup_path: Optional[Path | str] = None) -> Path:
    # 1. Inspect source database and verify existence
    # 2. Generate timestamped snapshot: setu_netra_backup_YYYYMMDD_HHMMSS.db
    # 3. Synchronously copy primary database file
    # 4. Copy WAL (-wal) and shared memory (-shm) files if present
    # 5. Compute cryptographic SHA-256 checksum of backup
```

### Verification Evidence
During automated testing ([`test_01_database_backup_utility`](file:///d:/Projects/Setu-Netra/tests/test_phase2_security_and_workspaces.py#L48)):
- A database with pre-existing records was created.
- `backup_database()` created `test_setu_backup_20261111_151101.db`.
- The backup database was independently connected to and inspected; records and table definitions matched the primary database bit-for-bit.

---

## 3. Migration Specifications

### Migration 001: `schema_migrations_table`
- **Purpose:** Establishes the authoritative schema version ledger.
- **`up()` Definition:**
  ```sql
  CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      applied_at TEXT NOT NULL
  );
  ```
- **`down()` Definition:**
  ```sql
  DROP TABLE IF EXISTS schema_migrations;
  ```

---

### Migration 002: `auth_workspaces_audit`
- **Purpose:** Provisions identity tables, workspace sandboxes, hashed sessions, tamper-evident audit ledger, and assigns workspace ownership to pre-existing document and session tables.
- **`up()` Definition:**
  1. **`users` Table:**
     ```sql
     CREATE TABLE IF NOT EXISTS users (
         user_id TEXT PRIMARY KEY,
         username TEXT UNIQUE NOT NULL,
         password_hash TEXT NOT NULL,
         display_name TEXT NOT NULL,
         role TEXT NOT NULL DEFAULT 'RESEARCHER',
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL
     );
     CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
     ```
  2. **`workspaces` Table:**
     ```sql
     CREATE TABLE IF NOT EXISTS workspaces (
         workspace_id TEXT PRIMARY KEY,
         name TEXT NOT NULL,
         description TEXT DEFAULT '',
         owner_id TEXT NOT NULL,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
     );
     ```
  3. **`workspace_members` Table:**
     ```sql
     CREATE TABLE IF NOT EXISTS workspace_members (
         workspace_id TEXT NOT NULL,
         user_id TEXT NOT NULL,
         role TEXT NOT NULL DEFAULT 'MEMBER',
         joined_at TEXT NOT NULL,
         PRIMARY KEY (workspace_id, user_id),
         FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
         FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
     );
     ```
  4. **`sessions` Table:**
     ```sql
     CREATE TABLE IF NOT EXISTS sessions (
         session_id_hash TEXT PRIMARY KEY,
         user_id TEXT NOT NULL,
         active_workspace_id TEXT NOT NULL,
         csrf_secret TEXT NOT NULL,
         created_at TEXT NOT NULL,
         expires_at TEXT NOT NULL,
         revoked_at TEXT,
         FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
         FOREIGN KEY (active_workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
     );
     CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
     ```
  5. **`audit_ledger` Table:**
     ```sql
     CREATE TABLE IF NOT EXISTS audit_ledger (
         entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
         prev_hash TEXT NOT NULL,
         entry_hash TEXT NOT NULL,
         action TEXT NOT NULL,
         user_id TEXT,
         workspace_id TEXT,
         timestamp_iso TEXT NOT NULL,
         details_json TEXT DEFAULT '{}'
     );
     CREATE INDEX IF NOT EXISTS idx_audit_prev_hash ON audit_ledger(prev_hash);
     ```
  6. **Table Alterations (Workspace Scoping):**
     ```sql
     ALTER TABLE documents ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default';
     CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id);

     ALTER TABLE document_blocks ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default';
     CREATE INDEX IF NOT EXISTS idx_blocks_workspace ON document_blocks(workspace_id);

     ALTER TABLE conversations ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default';
     CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id);
     ```
  7. **Default Seed Data:**
     - Institutional seed users:
       - `admin`: Role `OWNER` (initial hash generated via Argon2id)
       - `researcher`: Role `RESEARCHER`
       - `faculty`: Role `FACULTY_OBSERVER`
       - `guest`: Role `GUEST`
     - Institutional default workspace:
       - `workspace_id = 'default'` (Name: "Default Institutional Workspace", Owner: `usr_admin_000`)
     - Root audit entry:
       - `SYSTEM_INITIALIZE` event chained from root hash `0000000000000000000000000000000000000000000000000000000000000000`.

- **`down()` Definition:**
  1. Drops added tables: `audit_ledger`, `sessions`, `workspace_members`, `workspaces`, `users`.
  2. Drops indices: `idx_documents_workspace`, `idx_blocks_workspace`, `idx_conversations_workspace`.
  3. Drops `workspace_id` columns from `documents`, `document_blocks`, and `conversations`.

---

## 4. Legacy V1.1.0 Data Preservation Verification

A dedicated preservation test ([`test_03_v1_data_preservation_under_default_workspace`](file:///d:/Projects/Setu-Netra/tests/test_phase2_security_and_workspaces.py#L98)) was constructed and executed:
1. An unmigrated SQLite database was populated with legacy documents (`doc_id = 'doc_legacy_001'`, `file_path = 'sample.pdf'`, `file_hash = 'hash_legacy_123'`).
2. `apply_migrations()` was run on the live database.
3. The database was reopened using the updated `SQLiteDocumentStore`.
4. **Result:** The legacy document record was retrieved successfully with all metadata intact. Its `workspace_id` was automatically populated with `'default'`, making it instantly queryable within the default workspace without requiring data re-ingestion.

---

## 5. SQLite WAL Concurrency & PostgreSQL Migration Trigger Points

### 5.1 SQLite WAL Concurrency Profile
SETU-NETRA configures SQLite with:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

**Capabilities of SQLite WAL in SETU-NETRA:**
- **Concurrent Readers:** Unlimited reader connections can execute simultaneously without blocking each other or being blocked by a writer.
- **Single-Writer Constraint:** SQLite enforces a **single-writer boundary**. Only one process/thread may hold an exclusive write transaction at any given millisecond.
- **Busy Timeout:** `busy_timeout = 5000` instructs waiting writers to sleep and retry for up to 5.0 seconds before raising `sqlite3.OperationalError: database is locked`.

### 5.2 Criteria Requiring Migration to PostgreSQL
While SQLite WAL is optimal for consumer-hardware single-node deployments (eliminating external database daemon overhead), migration to PostgreSQL is strictly required when any of the following operational thresholds are met:

| Condition Metric | SQLite Threshold (Upper Limit) | Action Upon Exceeding Threshold |
|---|---|---|
| **Write Transaction Concurrency** | $> 15\text{ writes/second}$ | Transition to PostgreSQL to unlock row-level locking (MVCC). |
| **Concurrent Active Mutating Users** | $> 20\text{ simultaneous users}$ | Transition to PostgreSQL connection pool (pgbouncer). |
| **Document Database Size** | $> 10\text{ GB}$ (millions of blocks) | Transition to PostgreSQL with partitioned tables and pgvector. |
| **Multi-Node Deployment** | $> 1\text{ host machine}$ | SQLite cannot safely share WAL files over NFS/CIFS. Networked PostgreSQL mandatory. |
| **Granular Transaction Auditing** | External audit streaming | Transition to PostgreSQL write-ahead log replication (Debezium/CDC). |
