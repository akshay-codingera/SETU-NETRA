"""
migrations.py: Versioned, non-destructive, and reversible SQLite migration engine for SETU-NETRA.
"""

import datetime
import hashlib
import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def backup_database(db_path: Path | str, backup_path: Optional[Path | str] = None) -> Path:
    """Create a verified, WAL-safe online backup of the SQLite database using native backup API."""
    src = Path(db_path)
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        return src

    if backup_path is None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = src.parent / f"{src.stem}_backup_{timestamp}{src.suffix}"
    dst = Path(backup_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # WAL-safe online backup using SQLite's native backup API
    src_conn = sqlite3.connect(str(src), check_same_thread=False)
    try:
        try:
            src_conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except Exception:
            pass
        dst_conn = sqlite3.connect(str(dst), check_same_thread=False)
        try:
            src_conn.backup(dst_conn, pages=100)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    logger.info(f"WAL-safe database backup created: {dst} (SHA256: {compute_file_sha256(dst)})")
    return dst


class Migration:
    """Represents a single versioned database migration with up() and down() steps."""

    def __init__(
        self,
        version: int,
        name: str,
        up_fn: Callable[[sqlite3.Connection], None],
        down_fn: Callable[[sqlite3.Connection], None],
    ):
        self.version = version
        self.name = name
        self.up = up_fn
        self.down = down_fn


# -----------------------------------------------------------------------------
# Migration 1: Schema Tracking Table
# -----------------------------------------------------------------------------
def _m001_up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
    """)


def _m001_down(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS schema_migrations;")


# -----------------------------------------------------------------------------
# Migration 2: Users, Workspaces, Sessions, Audit Ledger & Workspace Scoping
# -----------------------------------------------------------------------------
def _m002_up(conn: sqlite3.Connection) -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Users Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'RESEARCHER',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

    # 2. Workspaces Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    """)

    # 3. Workspace Members Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'MEMBER',
            joined_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    """)

    # 4. Sessions Table
    conn.execute("""
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
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);")

    # 5. Tamper-Evident Audit Ledger Table
    conn.execute("""
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
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_prev_hash ON audit_ledger(prev_hash);")

    # 6. Add workspace_id columns to pre-existing tables if missing
    def _column_exists(table: str, col: str) -> bool:
        cursor = conn.execute(f"PRAGMA table_info({table});")
        return any(row[1] == col for row in cursor.fetchall())

    for target_table in ["documents", "document_blocks", "conversations"]:
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{target_table}';")
        if cursor.fetchone():
            if not _column_exists(target_table, "workspace_id"):
                conn.execute(f"ALTER TABLE {target_table} ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default';")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{target_table}_workspace ON {target_table}(workspace_id);")

    # 7. Seed System Users & Default Workspace
    # Pre-computed Argon2id hashes for initial default roles (passwords can be changed via profile)
    # AdminPassword123! -> $argon2id$v=19$m=65536,t=3,p=4$vQhW...
    # We will import hash_password from password module to ensure consistent Argon2id generation
    from setu_netra.auth.password import hash_password

    admin_hash = hash_password("AdminPassword123!")
    researcher_hash = hash_password("ResearcherPass123!")
    faculty_hash = hash_password("FacultyObserver123!")
    guest_hash = hash_password("GuestRestricted123!")

    # Insert default users if not already present
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, username, password_hash, display_name, role, created_at, updated_at)
        VALUES 
        ('usr_admin_000', 'admin', ?, 'System Administrator', 'OWNER', ?, ?),
        ('usr_researcher_000', 'researcher', ?, 'Principal Researcher', 'RESEARCHER', ?, ?),
        ('usr_faculty_000', 'faculty', ?, 'Faculty Reviewer', 'FACULTY_OBSERVER', ?, ?),
        ('usr_guest_000', 'guest', ?, 'Guest Evaluator', 'GUEST', ?, ?);
    """, (admin_hash, now_iso, now_iso, researcher_hash, now_iso, now_iso, faculty_hash, now_iso, now_iso, guest_hash, now_iso, now_iso))

    # Insert default workspace
    conn.execute("""
        INSERT OR IGNORE INTO workspaces (workspace_id, name, description, owner_id, created_at, updated_at)
        VALUES ('default', 'Default Institutional Workspace', 'Primary workspace for V1.1.0 documents', 'usr_admin_000', ?, ?);
    """, (now_iso, now_iso))

    # Ensure admin, researcher, and faculty are members of default workspace
    conn.execute("""
        INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, joined_at)
        VALUES 
        ('default', 'usr_admin_000', 'OWNER', ?),
        ('default', 'usr_researcher_000', 'MEMBER', ?),
        ('default', 'usr_faculty_000', 'VIEWER', ?);
    """, (now_iso, now_iso, now_iso))

    # Seed initial root audit log entry using AuditLedger to ensure cryptographic continuity
    cursor = conn.execute("SELECT COUNT(*) FROM audit_ledger;")
    if cursor.fetchone()[0] == 0:
        from setu_netra.auth.audit import AuditLedger
        AuditLedger.log_event(
            conn,
            action="SYSTEM_INITIALIZE",
            user_id="usr_admin_000",
            workspace_id="default",
            details={"message": "Audit ledger initialized"},
        )


def _m002_down(conn: sqlite3.Connection) -> None:
    # Drop added tables
    conn.execute("DROP TABLE IF EXISTS audit_ledger;")
    conn.execute("DROP TABLE IF EXISTS sessions;")
    conn.execute("DROP TABLE IF EXISTS workspace_members;")
    conn.execute("DROP TABLE IF EXISTS workspaces;")
    conn.execute("DROP TABLE IF EXISTS users;")

    # Drop columns from existing tables in SQLite 3.35+
    for target_table in ["documents", "document_blocks", "conversations"]:
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{target_table}';")
        if cursor.fetchone():
            try:
                conn.execute(f"DROP INDEX IF EXISTS idx_{target_table}_workspace;")
                conn.execute(f"DROP INDEX IF EXISTS idx_docs_workspace;")
                conn.execute(f"DROP INDEX IF EXISTS idx_blocks_workspace;")
                conn.execute(f"ALTER TABLE {target_table} DROP COLUMN workspace_id;")
            except Exception as e:
                logger.warning(f"Could not drop column workspace_id from {target_table}: {e}")


# Migration Registry
ALL_MIGRATIONS: List[Migration] = [
    Migration(version=1, name="schema_migrations_table", up_fn=_m001_up, down_fn=_m001_down),
    Migration(version=2, name="auth_workspaces_audit", up_fn=_m002_up, down_fn=_m002_down),
]


def apply_migrations(db_path: Path | str) -> int:
    """Apply all pending migrations to the SQLite database. Returns count of applied migrations."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    try:
        with conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 5000;")

            # 1. Ensure migrations table exists
            _m001_up(conn)

            # 2. Query already applied versions
            cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
            applied_versions = {row["version"] for row in cursor.fetchall()}

            applied_count = 0
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            for migration in ALL_MIGRATIONS:
                if migration.version not in applied_versions:
                    logger.info(f"Applying migration {migration.version}: {migration.name}...")
                    migration.up(conn)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                        (migration.version, migration.name, now_iso),
                    )
                    applied_count += 1
                    logger.info(f"Successfully applied migration {migration.version}: {migration.name}.")

            return applied_count
    finally:
        conn.close()


def rollback_migration(db_path: Path | str, target_version: int = 0) -> int:
    """Roll back migrations down to target_version. Returns count of rolled back migrations."""
    db_file = Path(db_path)
    if not db_file.exists():
        return 0

    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = OFF;")  # Disable foreign keys during rollback

            cursor = conn.execute("SELECT version, name FROM schema_migrations ORDER BY version DESC;")
            applied = cursor.fetchall()
            
            rolled_back_count = 0
            migration_map = {m.version: m for m in ALL_MIGRATIONS}

            for row in applied:
                ver = row["version"]
                if ver > target_version:
                    m = migration_map.get(ver)
                    if m:
                        logger.info(f"Rolling back migration {ver}: {m.name}...")
                        m.down(conn)
                        conn.execute("DELETE FROM schema_migrations WHERE version = ?;", (ver,))
                        rolled_back_count += 1
                        logger.info(f"Successfully rolled back migration {ver}: {m.name}.")

            return rolled_back_count
    finally:
        conn.close()
