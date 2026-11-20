"""
service.py: High-level authentication, session rotation, workspace sandboxing,
and RBAC authorization service backed by SQLite.
"""

import datetime
import hashlib
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from setu_netra.auth.audit import AuditLedger
from setu_netra.auth.password import hash_password, verify_password
from setu_netra.auth.roles import Permission, UserRole, has_permission
from setu_netra.auth.session import (
    DEFAULT_SESSION_DURATION_SECONDS,
    generate_csrf_secret,
    generate_session_token,
    hash_token,
)

logger = logging.getLogger(__name__)


@dataclass
class UserRecord:
    user_id: str
    username: str
    display_name: str
    role: UserRole
    created_at: str
    updated_at: str


@dataclass
class WorkspaceRecord:
    workspace_id: str
    name: str
    description: str
    owner_id: str
    created_at: str
    updated_at: str


@dataclass
class SessionRecord:
    session_id_hash: str
    user_id: str
    active_workspace_id: str
    csrf_secret: str
    created_at: str
    expires_at: str
    revoked_at: Optional[str] = None


@dataclass
class AuthenticatedSession:
    user: UserRecord
    session: SessionRecord
    raw_token: Optional[str] = None


class AuthService:
    """Manages identity lifecycle, credential verification, and workspace boundary enforcement."""

    def __init__(self, db_path: Path | str = "output/setu_netra.db"):
        self.db_path = Path(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def register_user(
        self,
        username: str,
        password: str,
        display_name: str,
        role: UserRole | str = UserRole.RESEARCHER,
    ) -> UserRecord:
        """Register a new user, hash password using Argon2id, and provision a personal workspace."""
        clean_user = username.strip().lower()
        if len(clean_user) < 3 or not all(c.isalnum() or c == '_' for c in clean_user):
            raise ValueError("Username must be alphanumeric (underscores allowed) and at least 3 characters long.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        user_role = UserRole(role) if isinstance(role, str) else role
        pw_hash = hash_password(password)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        user_id = f"usr_{uuid.uuid4().hex[:10]}"

        conn = self._get_conn()
        try:
            with conn:
                # Security Check: Prevent privilege escalation via public registration
                if user_role in (UserRole.OWNER, UserRole.FACULTY_OBSERVER):
                    cur = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'OWNER';")
                    owner_count = cur.fetchone()[0]
                    if owner_count > 0:
                        raise ValueError(f"Registration cannot grant privileged role '{user_role.value}'. Administrator assignment required.")

                # 1. Insert User
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, password_hash, display_name, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (user_id, clean_user, pw_hash, display_name.strip(), user_role.value, now_iso, now_iso),
                )

                # 2. Automatically create personal workspace for researcher / owner
                ws_id = f"ws_{clean_user}"
                ws_name = f"{display_name.strip()}'s Workspace"
                conn.execute(
                    """
                    INSERT INTO workspaces (workspace_id, name, description, owner_id, created_at, updated_at)
                    VALUES (?, ?, 'Personal research workspace', ?, ?, ?);
                    """,
                    (ws_id, ws_name, user_id, now_iso, now_iso),
                )

                # 3. Add to workspace_members
                conn.execute(
                    """
                    INSERT INTO workspace_members (workspace_id, user_id, role, joined_at)
                    VALUES (?, ?, 'OWNER', ?);
                    """,
                    (ws_id, user_id, now_iso),
                )

                # 4. Also add to default workspace as member
                conn.execute(
                    """
                    INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, joined_at)
                    VALUES ('default', ?, 'MEMBER', ?);
                    """,
                    (user_id, now_iso),
                )

                # 5. Log in tamper-evident audit ledger
                AuditLedger.log_event(
                    conn=conn,
                    action="USER_REGISTER",
                    user_id=user_id,
                    workspace_id=ws_id,
                    details={"username": clean_user, "role": user_role.value},
                )

            return UserRecord(
                user_id=user_id,
                username=clean_user,
                display_name=display_name.strip(),
                role=user_role,
                created_at=now_iso,
                updated_at=now_iso,
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{clean_user}' is already registered.")
        finally:
            conn.close()

    def authenticate_user(self, username: str, password: str) -> Tuple[Optional[UserRecord], Optional[str]]:
        """Verify user credentials against Argon2id hash. Returns (UserRecord, error_msg)."""
        clean_user = username.strip().lower()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT user_id, username, password_hash, display_name, role, created_at, updated_at FROM users WHERE username = ?;",
                (clean_user,),
            )
            row = cursor.fetchone()
            if not row:
                AuditLedger.log_event(conn, action="AUTH_FAILED", details={"username": clean_user, "reason": "User not found"})
                return None, "Invalid username or password."

            if not verify_password(password, row["password_hash"]):
                AuditLedger.log_event(conn, action="AUTH_FAILED", user_id=row["user_id"], details={"username": clean_user, "reason": "Password mismatch"})
                return None, "Invalid username or password."

            user = UserRecord(
                user_id=row["user_id"],
                username=row["username"],
                display_name=row["display_name"],
                role=UserRole(row["role"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            AuditLedger.log_event(conn, action="AUTH_LOGIN_SUCCESS", user_id=user.user_id, details={"username": user.username})
            return user, None
        finally:
            conn.close()

    def create_session(
        self,
        user_id: str,
        active_workspace_id: Optional[str] = None,
        duration_seconds: int = DEFAULT_SESSION_DURATION_SECONDS,
    ) -> Tuple[str, SessionRecord]:
        """Generate a cryptographically secure 256-bit session token and rotate prior active sessions."""
        conn = self._get_conn()
        try:
            with conn:
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                now_iso = now_dt.isoformat()
                expires_iso = (now_dt + datetime.timedelta(seconds=duration_seconds)).isoformat()

                # Session Rotation: Invalidate prior sessions for this user
                conn.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL;",
                    (now_iso, user_id),
                )

                # Determine active workspace
                if not active_workspace_id:
                    cursor = conn.execute(
                        "SELECT workspace_id FROM workspace_members WHERE user_id = ? ORDER BY (workspace_id = 'default') ASC LIMIT 1;",
                        (user_id,),
                    )
                    row = cursor.fetchone()
                    active_workspace_id = row[0] if row else "default"

                raw_token = generate_session_token()
                token_hash = hash_token(raw_token)
                csrf_secret = generate_csrf_secret()

                conn.execute(
                    """
                    INSERT INTO sessions (session_id_hash, user_id, active_workspace_id, csrf_secret, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (token_hash, user_id, active_workspace_id, csrf_secret, now_iso, expires_iso),
                )

                AuditLedger.log_event(
                    conn,
                    action="SESSION_CREATED",
                    user_id=user_id,
                    workspace_id=active_workspace_id,
                    details={"expires_at": expires_iso},
                )

            session = SessionRecord(
                session_id_hash=token_hash,
                user_id=user_id,
                active_workspace_id=active_workspace_id,
                csrf_secret=csrf_secret,
                created_at=now_iso,
                expires_at=expires_iso,
            )
            return raw_token, session
        finally:
            conn.close()

    def get_session_by_token(self, raw_token: str) -> Optional[AuthenticatedSession]:
        """Resolve a raw session token to an active user session."""
        if not raw_token:
            return None
        token_hash = hash_token(raw_token)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT s.session_id_hash, s.user_id, s.active_workspace_id, s.csrf_secret, s.created_at as s_created, s.expires_at, s.revoked_at,
                       u.username, u.display_name, u.role, u.created_at as u_created, u.updated_at as u_updated
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.session_id_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?;
                """,
                (token_hash, now_iso),
            )
            row = cursor.fetchone()
            if not row:
                return None

            user = UserRecord(
                user_id=row["user_id"],
                username=row["username"],
                display_name=row["display_name"],
                role=UserRole(row["role"]),
                created_at=row["u_created"],
                updated_at=row["u_updated"],
            )
            session = SessionRecord(
                session_id_hash=row["session_id_hash"],
                user_id=row["user_id"],
                active_workspace_id=row["active_workspace_id"],
                csrf_secret=row["csrf_secret"],
                created_at=row["s_created"],
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
            )
            return AuthenticatedSession(user=user, session=session, raw_token=raw_token)
        finally:
            conn.close()

    def revoke_session(self, raw_token: str) -> bool:
        """Revoke active session token (Logout)."""
        if not raw_token:
            return False
        token_hash = hash_token(raw_token)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("SELECT user_id, active_workspace_id FROM sessions WHERE session_id_hash = ?;", (token_hash,))
                row = cursor.fetchone()
                if not row:
                    return False
                user_id = row[0]
                workspace_id = row[1]

                conn.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE session_id_hash = ?;",
                    (now_iso, token_hash),
                )
                AuditLedger.log_event(conn, action="AUTH_LOGOUT", user_id=user_id, workspace_id=workspace_id)
            return True
        finally:
            conn.close()

    def create_workspace(self, name: str, description: str, owner_id: str) -> WorkspaceRecord:
        """Create a new workspace namespace bound to owner."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Workspace name cannot be empty.")
        
        ws_id = f"ws_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO workspaces (workspace_id, name, description, owner_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (ws_id, clean_name, description.strip(), owner_id, now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO workspace_members (workspace_id, user_id, role, joined_at)
                    VALUES (?, ?, 'OWNER', ?);
                    """,
                    (ws_id, owner_id, now_iso),
                )
                AuditLedger.log_event(
                    conn,
                    action="WORKSPACE_CREATE",
                    user_id=owner_id,
                    workspace_id=ws_id,
                    details={"name": clean_name},
                )

            return WorkspaceRecord(
                workspace_id=ws_id,
                name=clean_name,
                description=description.strip(),
                owner_id=owner_id,
                created_at=now_iso,
                updated_at=now_iso,
            )
        finally:
            conn.close()

    def get_user_workspaces(self, user_id: str, role: UserRole) -> List[WorkspaceRecord]:
        """Return all workspaces accessible to user."""
        conn = self._get_conn()
        try:
            if role == UserRole.OWNER or role == UserRole.FACULTY_OBSERVER:
                # Owners and Faculty can see all workspaces across the platform
                cursor = conn.execute(
                    "SELECT workspace_id, name, description, owner_id, created_at, updated_at FROM workspaces ORDER BY created_at DESC;"
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT w.workspace_id, w.name, w.description, w.owner_id, w.created_at, w.updated_at
                    FROM workspaces w
                    JOIN workspace_members m ON w.workspace_id = m.workspace_id
                    WHERE m.user_id = ?
                    ORDER BY w.created_at DESC;
                    """,
                    (user_id,),
                )
            return [
                WorkspaceRecord(
                    workspace_id=row["workspace_id"],
                    name=row["name"],
                    description=row["description"],
                    owner_id=row["owner_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def verify_workspace_access(
        self,
        user_id: str,
        role: UserRole,
        workspace_id: str,
        require_write: bool = False,
    ) -> bool:
        """Object-level authorization check confirming user can access the target workspace."""
        if role == UserRole.OWNER:
            return True
        if role == UserRole.FACULTY_OBSERVER:
            # Faculty observer has read-only access to all workspaces
            return not require_write

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?;",
                (workspace_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return False
            member_role = row[0]
            if require_write and member_role == "VIEWER":
                return False
            return True
        finally:
            conn.close()

    def switch_active_workspace(self, session_id_hash: str, user_id: str, role: UserRole, new_workspace_id: str) -> bool:
        """Change the active workspace for the current session."""
        if not self.verify_workspace_access(user_id, role, new_workspace_id, require_write=False):
            return False

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    "UPDATE sessions SET active_workspace_id = ? WHERE session_id_hash = ?;",
                    (new_workspace_id, session_id_hash),
                )
                AuditLedger.log_event(
                    conn,
                    action="WORKSPACE_SWITCH",
                    user_id=user_id,
                    workspace_id=new_workspace_id,
                )
            return True
        finally:
            conn.close()
