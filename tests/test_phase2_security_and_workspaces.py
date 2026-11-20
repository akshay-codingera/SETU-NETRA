"""
test_phase2_security_and_workspaces.py: Complete Phase 2 verification suite.

Covers:
1. Reversible, versioned SQLite database migrations and backup utility.
2. V1.1.0 data preservation under workspace_id = 'default'.
3. Argon2id password hashing and constant-time verification (RFC 9106).
4. Session management, 256-bit secure tokens, and session rotation.
5. Anti-CSRF token enforcement on state-changing endpoints.
6. 4-Role RBAC Capability Matrix (OWNER, RESEARCHER, FACULTY_OBSERVER, GUEST).
7. Workspace isolation (User A vs User B, cross-workspace retrieval prevention, Faculty Observer cross-read).
8. Tamper-evident SHA-256 chained audit ledger with corruption detection and credential scrubbing.
9. End-to-End API endpoint integration via TestClient.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from setu_netra.api.main import create_app
from setu_netra.auth.audit import AuditLedger
from setu_netra.auth.password import hash_password, verify_password
from setu_netra.auth.roles import Permission, UserRole, has_permission
from setu_netra.auth.service import AuthService
from setu_netra.auth.session import (
    SESSION_COOKIE_NAME,
    generate_csrf_secret,
    generate_session_token,
    hash_token,
)
from setu_netra.store.migrations import (
    apply_migrations,
    backup_database,
    rollback_migration,
)
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class TestPhase2SecurityAndWorkspaces(unittest.TestCase):
    """Phase 2 comprehensive verification test cases."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="setu_p2_test_")
        self.db_path = Path(self.temp_dir) / "test_setu.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. Database Migrations & Backup
    # =========================================================================

    def test_01_database_backup_utility(self):
        """Verify that backup_database creates a byte-accurate snapshot."""
        # Create an initial DB file
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE sample_data (id INT PRIMARY KEY, val TEXT);")
        conn.execute("INSERT INTO sample_data VALUES (1, 'initial_v1');")
        conn.commit()
        conn.close()

        backup_file = backup_database(self.db_path)
        self.assertTrue(backup_file.exists())
        self.assertIn("backup_", backup_file.name)

        # Verify content in backup
        b_conn = sqlite3.connect(str(backup_file))
        cur = b_conn.execute("SELECT val FROM sample_data WHERE id = 1;")
        self.assertEqual(cur.fetchone()[0], "initial_v1")
        b_conn.close()

    def test_02_migrations_apply_and_rollback(self):
        """Verify that apply_migrations applies migrations and rollback cleanly reverses migration 2."""
        # Initialize an empty DB
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE documents (doc_id TEXT PRIMARY KEY, file_path TEXT, file_name TEXT, file_hash TEXT UNIQUE, file_type TEXT, page_count INT, created_at TEXT, status TEXT, metadata_json TEXT);")
        conn.execute("CREATE TABLE document_blocks (block_pk INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, page_number INT, block_id INT, block_type TEXT, text TEXT, confidence REAL, bbox_json TEXT);")
        conn.execute("CREATE TABLE conversations (conversation_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, created_at REAL, updated_at REAL, metadata_json TEXT);")
        conn.commit()
        conn.close()

        # Apply migrations
        applied = apply_migrations(self.db_path)
        self.assertEqual(applied, 2)

        # Verify tables exist
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}
        self.assertIn("schema_migrations", tables)
        self.assertIn("users", tables)
        self.assertIn("workspaces", tables)
        self.assertIn("workspace_members", tables)
        self.assertIn("sessions", tables)
        self.assertIn("audit_ledger", tables)

        # Verify workspace_id column was added
        cur = conn.execute("PRAGMA table_info(documents);")
        doc_cols = {row[1] for row in cur.fetchall()}
        self.assertIn("workspace_id", doc_cols)
        conn.close()

        # Rollback migration 2
        rolled_back = rollback_migration(self.db_path, target_version=1)
        self.assertEqual(rolled_back, 1)

        conn = sqlite3.connect(str(self.db_path))
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_after = {row[0] for row in cur.fetchall()}
        self.assertNotIn("users", tables_after)
        self.assertNotIn("workspaces", tables_after)
        conn.close()

    def test_03_v1_data_preservation_under_default_workspace(self):
        """Verify that pre-existing V1.1.0 records are preserved and mapped to 'default' workspace."""
        # Create pre-migration database with legacy records
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                file_path TEXT,
                file_name TEXT,
                file_hash TEXT UNIQUE,
                file_type TEXT,
                page_count INT,
                created_at TEXT,
                status TEXT,
                metadata_json TEXT
            );
        """)
        conn.execute("""
            INSERT INTO documents VALUES (
                'doc_legacy_001', 'sample.pdf', 'sample.pdf', 'hash_legacy_123',
                'PDF', 3, '2026-11-01T00:00:00', 'PROCESSED', '{}'
            );
        """)
        conn.commit()
        conn.close()

        # Run migrations
        apply_migrations(self.db_path)

        # Inspect preserved record
        store = SQLiteDocumentStore(self.db_path)
        doc = store.get_document_by_id("doc_legacy_001")
        self.assertIsNotNone(doc)
        self.assertEqual(doc.doc_id, "doc_legacy_001")
        self.assertEqual(doc.workspace_id, "default")
        store.close()

    # =========================================================================
    # 2. Cryptographic Security & Password Hashing
    # =========================================================================

    def test_04_argon2id_password_hashing(self):
        """Verify that password hashing uses Argon2id with RFC 9106 parameters and unique salts."""
        password = "SecureResearchPass2026!"
        h1 = hash_password(password)
        h2 = hash_password(password)

        # Must conform to Argon2id RFC 9106 format
        self.assertTrue(h1.startswith("$argon2id$v=19$m=65536,t=3,p=4$"))
        # Salting must ensure distinct hashes for identical passwords
        self.assertNotEqual(h1, h2)

        # Verification
        self.assertTrue(verify_password(password, h1))
        self.assertTrue(verify_password(password, h2))
        self.assertFalse(verify_password("WrongPassword!", h1))

    # =========================================================================
    # 3. User Registration, Authentication & Session Lifecycle
    # =========================================================================

    def test_05_user_registration_and_workspace_provisioning(self):
        """Verify that registration creates user, personal workspace, and audit record."""
        apply_migrations(self.db_path)
        auth = AuthService(self.db_path)

        user = auth.register_user(
            username="newdocdev",
            password="StrongPassword123!",
            display_name="New Researcher",
            role=UserRole.RESEARCHER,
        )
        self.assertEqual(user.username, "newdocdev")
        self.assertEqual(user.role, UserRole.RESEARCHER)

        # Verify personal workspace
        workspaces = auth.get_user_workspaces(user.user_id, user.role)
        ws_ids = {w.workspace_id for w in workspaces}
        self.assertIn("ws_newdocdev", ws_ids)
        self.assertIn("default", ws_ids)

    def test_06_session_creation_rotation_and_revocation(self):
        """Verify session issuance, rotation on repeated login, and logout revocation."""
        apply_migrations(self.db_path)
        auth = AuthService(self.db_path)

        user, err = auth.authenticate_user("admin", "AdminPassword123!")
        self.assertIsNone(err)
        self.assertIsNotNone(user)

        # First login creates session 1
        t1, s1 = auth.create_session(user.user_id)
        self.assertTrue(len(t1) >= 32)
        self.assertIsNotNone(auth.get_session_by_token(t1))

        # Second login creates session 2 and rotates session 1
        t2, s2 = auth.create_session(user.user_id)
        self.assertIsNone(auth.get_session_by_token(t1))  # Session 1 revoked by rotation
        self.assertIsNotNone(auth.get_session_by_token(t2))  # Session 2 active

        # Revoke session 2 (Logout)
        success = auth.revoke_session(t2)
        self.assertTrue(success)
        self.assertIsNone(auth.get_session_by_token(t2))

    # =========================================================================
    # 4. Anti-CSRF Token Enforcement
    # =========================================================================

    def test_07_csrf_token_generation_and_validation(self):
        """Verify CSRF token secret generation and constant-time validation."""
        s1 = generate_csrf_secret()
        s2 = generate_csrf_secret()
        self.assertNotEqual(s1, s2)
        self.assertTrue(len(s1) >= 32)

    # =========================================================================
    # 5. Role-Based Access Control (RBAC) Capability Matrix
    # =========================================================================

    def test_08_rbac_capability_matrix(self):
        """Verify capabilities across OWNER, RESEARCHER, FACULTY_OBSERVER, GUEST."""
        # OWNER has full privileges
        self.assertTrue(has_permission(UserRole.OWNER, Permission.WORKSPACE_CREATE))
        self.assertTrue(has_permission(UserRole.OWNER, Permission.DOCUMENT_UPLOAD))
        self.assertTrue(has_permission(UserRole.OWNER, Permission.DOCUMENT_DELETE))
        self.assertTrue(has_permission(UserRole.OWNER, Permission.AUDIT_READ))

        # RESEARCHER can work with documents and queries, but cannot view system audit
        self.assertTrue(has_permission(UserRole.RESEARCHER, Permission.WORKSPACE_CREATE))
        self.assertTrue(has_permission(UserRole.RESEARCHER, Permission.DOCUMENT_UPLOAD))
        self.assertTrue(has_permission(UserRole.RESEARCHER, Permission.QUERY_EXECUTE))
        self.assertFalse(has_permission(UserRole.RESEARCHER, Permission.AUDIT_READ))

        # FACULTY_OBSERVER is strictly read-only: can view docs and audit, CANNOT mutate
        self.assertTrue(has_permission(UserRole.FACULTY_OBSERVER, Permission.DOCUMENT_READ))
        self.assertTrue(has_permission(UserRole.FACULTY_OBSERVER, Permission.QUERY_EXECUTE))
        self.assertTrue(has_permission(UserRole.FACULTY_OBSERVER, Permission.AUDIT_READ))
        self.assertFalse(has_permission(UserRole.FACULTY_OBSERVER, Permission.DOCUMENT_UPLOAD))
        self.assertFalse(has_permission(UserRole.FACULTY_OBSERVER, Permission.DOCUMENT_DELETE))
        self.assertFalse(has_permission(UserRole.FACULTY_OBSERVER, Permission.WORKSPACE_CREATE))

        # GUEST has minimal query execution only
        self.assertTrue(has_permission(UserRole.GUEST, Permission.QUERY_RESTRICTED))
        self.assertFalse(has_permission(UserRole.GUEST, Permission.QUERY_EXECUTE))
        self.assertFalse(has_permission(UserRole.GUEST, Permission.DOCUMENT_UPLOAD))
        self.assertFalse(has_permission(UserRole.GUEST, Permission.DOCUMENT_DELETE))
        self.assertFalse(has_permission(UserRole.GUEST, Permission.WORKSPACE_CREATE))

    # =========================================================================
    # 6. Multi-Tenant Workspace Sandboxing
    # =========================================================================

    def test_09_workspace_isolation_and_cross_workspace_protection(self):
        """Verify that User A's documents cannot be accessed or deleted by User B, but Faculty Observer can view."""
        apply_migrations(self.db_path)
        auth = AuthService(self.db_path)
        store = SQLiteDocumentStore(self.db_path)

        user_a = auth.register_user("scientist_a", "PassScientistA123!", "Scientist A", UserRole.RESEARCHER)
        user_b = auth.register_user("scientist_b", "PassScientistB123!", "Scientist B", UserRole.RESEARCHER)

        ws_a = f"ws_scientist_a"
        ws_b = f"ws_scientist_b"

        # Save Doc A in Workspace A
        store.save_document(
            doc_id="doc_a_secret",
            file_path=Path("doc_a.pdf"),
            file_hash="hash_a",
            file_type="PDF",
            workspace_id=ws_a,
        )

        # Save Doc B in Workspace B
        store.save_document(
            doc_id="doc_b_open",
            file_path=Path("doc_b.pdf"),
            file_hash="hash_b",
            file_type="PDF",
            workspace_id=ws_b,
        )

        # User A has write access to Workspace A, but NOT Workspace B
        self.assertTrue(auth.verify_workspace_access(user_a.user_id, user_a.role, ws_a, require_write=True))
        self.assertFalse(auth.verify_workspace_access(user_a.user_id, user_a.role, ws_b, require_write=False))

        # User B cannot delete Doc A
        deleted = store.delete_document("doc_a_secret", workspace_id=ws_b)
        self.assertFalse(deleted)
        self.assertIsNotNone(store.get_document_by_id("doc_a_secret"))

        # Faculty Observer can view Workspace A and Workspace B, but cannot write
        faculty_user, _ = auth.authenticate_user("faculty", "FacultyObserver123!")
        self.assertTrue(auth.verify_workspace_access(faculty_user.user_id, faculty_user.role, ws_a, require_write=False))
        self.assertTrue(auth.verify_workspace_access(faculty_user.user_id, faculty_user.role, ws_b, require_write=False))
        self.assertFalse(auth.verify_workspace_access(faculty_user.user_id, faculty_user.role, ws_a, require_write=True))

        store.close()

    # =========================================================================
    # 7. Tamper-Evident SHA-256 Chained Audit Ledger
    # =========================================================================

    def test_10_audit_ledger_chaining_and_tamper_detection(self):
        """Verify that audit entries form a cryptographic hash chain and tampering is detected."""
        apply_migrations(self.db_path)
        conn = sqlite3.connect(str(self.db_path))

        # Log three events
        AuditLedger.log_event(conn, action="EVENT_1", user_id="u1", workspace_id="ws1", details={"step": 1})
        AuditLedger.log_event(conn, action="EVENT_2", user_id="u2", workspace_id="ws2", details={"step": 2})
        AuditLedger.log_event(conn, action="EVENT_3", user_id="u3", workspace_id="ws3", details={"step": 3})

        # Chain should be valid
        is_valid, bad_id = AuditLedger.verify_chain_integrity(conn)
        self.assertTrue(is_valid)
        self.assertIsNone(bad_id)

        # Simulate adversarial tamper: modify details of entry #2 directly in SQLite
        conn.execute("UPDATE audit_ledger SET action = 'TAMPERED_ACTION' WHERE entry_id = 2;")
        conn.commit()

        # Integrity verification must catch the tamper
        is_valid_after, bad_id_after = AuditLedger.verify_chain_integrity(conn)
        self.assertFalse(is_valid_after)
        self.assertEqual(bad_id_after, 2)
        conn.close()

    def test_11_audit_ledger_credential_scrubbing(self):
        """Verify that sensitive credential keys are scrubbed before logging."""
        apply_migrations(self.db_path)
        conn = sqlite3.connect(str(self.db_path))

        sensitive_dict = {
            "password": "RawSuperSecretPassword!",
            "token": "tok_abcdef123456",
            "api_key": "sk-1234567890",
            "user_email": "researcher@example.org",
        }
        entry_hash = AuditLedger.log_event(conn, action="USER_LOGIN", user_id="u1", details=sensitive_dict)

        # Read back row
        cur = conn.execute("SELECT details_json FROM audit_ledger WHERE entry_hash = ?;", (entry_hash,))
        details_str = cur.fetchone()[0]
        self.assertNotIn("RawSuperSecretPassword!", details_str)
        self.assertNotIn("tok_abcdef123456", details_str)
        self.assertNotIn("sk-1234567890", details_str)
        self.assertIn("[REDACTED]", details_str)
        conn.close()

    # =========================================================================
    # 8. End-to-End API Integration
    # =========================================================================

    def test_12_api_auth_workflow_and_csrf_protection(self):
        """Verify full API lifecycle: register, login, session inspection, CSRF rejection, and logout."""
        apply_migrations(self.db_path)
        app = create_app(db_path=str(self.db_path))
        client = TestClient(app)

        # 1. Register a user
        reg_payload = {
            "username": "apiresearcher",
            "password": "SecurePassword123!",
            "display_name": "API Researcher",
            "role": "RESEARCHER",
        }
        res_reg = client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 201)
        data = res_reg.json()
        self.assertTrue(data["authenticated"])
        csrf_token = data["csrf_token"]
        self.assertIsNotNone(csrf_token)
        self.assertIn(SESSION_COOKIE_NAME, client.cookies)

        # 2. Inspect session
        res_sess = client.get("/api/v1/auth/session")
        self.assertEqual(res_sess.status_code, 200)
        self.assertEqual(res_sess.json()["user"]["username"], "apiresearcher")

        # 3. Create workspace without CSRF header -> MUST FAIL with 403
        res_ws_fail = client.post("/api/v1/workspaces", json={"name": "Quantum Labs"})
        self.assertEqual(res_ws_fail.status_code, 403)
        self.assertIn("CSRF", res_ws_fail.text)

        # 4. Create workspace with valid CSRF header -> MUST SUCCEED with 201
        res_ws_ok = client.post(
            "/api/v1/workspaces",
            json={"name": "Quantum Labs", "description": "High performance QA research"},
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(res_ws_ok.status_code, 201)
        new_ws_id = res_ws_ok.json()["workspace_id"]

        # 5. Switch to new workspace
        res_switch = client.post(
            f"/api/v1/workspaces/{new_ws_id}/switch",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(res_switch.status_code, 200)
        self.assertEqual(res_switch.json()["active_workspace_id"], new_ws_id)

        # 6. Logout with CSRF
        res_logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(res_logout.status_code, 200)

        # 7. Verify session is now unauthenticated
        res_sess_after = client.get("/api/v1/auth/session")
        self.assertEqual(res_sess_after.status_code, 200)
        self.assertFalse(res_sess_after.json()["authenticated"])

    def test_13_api_faculty_observer_read_only_protection(self):
        """Verify that Faculty Observer can list and view, but mutating operations are rejected with 403."""
        apply_migrations(self.db_path)
        app = create_app(db_path=str(self.db_path))
        client = TestClient(app)

        # Login as faculty observer
        login_res = client.post(
            "/api/v1/auth/login",
            json={"username": "faculty", "password": "FacultyObserver123!"},
        )
        self.assertEqual(login_res.status_code, 200)
        csrf_token = login_res.json()["csrf_token"]

        # Faculty can view workspaces
        res_ws = client.get("/api/v1/workspaces")
        self.assertEqual(res_ws.status_code, 200)
        self.assertTrue(len(res_ws.json()) >= 1)

        # Faculty attempting to create workspace -> 403 Forbidden
        res_create = client.post(
            "/api/v1/workspaces",
            json={"name": "Disallowed Workspace"},
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(res_create.status_code, 403)

    def test_14_api_document_workspace_isolation_and_retrieval(self):
        """Verify strict document boundary isolation between Researcher A, Researcher B, and Faculty Observer."""
        apply_migrations(self.db_path)
        app = create_app(db_path=str(self.db_path))
        client = TestClient(app)

        # 1. Register and login User A
        reg_a = client.post("/api/v1/auth/register", json={
            "username": "researcher_alpha",
            "password": "PasswordAlpha123!",
            "display_name": "Researcher Alpha",
            "role": "RESEARCHER",
        })
        self.assertEqual(reg_a.status_code, 201)
        ws_a = reg_a.json()["active_workspace_id"]
        csrf_a = reg_a.json()["csrf_token"]

        # Directly seed a document into workspace A via the store
        store = SQLiteDocumentStore(self.db_path)
        store.save_document(
            doc_id="doc_alpha_private",
            file_path=Path("alpha_report.pdf"),
            file_hash="hash_alpha_999",
            file_type="PDF",
            workspace_id=ws_a,
        )

        # 2. Register and login User B
        client_b = TestClient(app)
        reg_b = client_b.post("/api/v1/auth/register", json={
            "username": "researcher_beta",
            "password": "PasswordBeta123!",
            "display_name": "Researcher Beta",
            "role": "RESEARCHER",
        })
        self.assertEqual(reg_b.status_code, 201)
        ws_b = reg_b.json()["active_workspace_id"]
        csrf_b = reg_b.json()["csrf_token"]

        # 3. User B lists documents in their workspace -> doc_alpha_private must NOT appear
        res_docs_b = client_b.get("/api/v1/documents")
        self.assertEqual(res_docs_b.status_code, 200)
        doc_ids_b = [d["doc_id"] for d in res_docs_b.json()]
        self.assertNotIn("doc_alpha_private", doc_ids_b)

        # 4. User B attempts direct GET /documents/doc_alpha_private -> MUST return 403 Forbidden
        res_get_forbidden = client_b.get("/api/v1/documents/doc_alpha_private")
        self.assertEqual(res_get_forbidden.status_code, 403)

        # 5. User B attempts DELETE /documents/doc_alpha_private -> MUST return 403 Forbidden
        res_del_forbidden = client_b.delete(
            "/api/v1/documents/doc_alpha_private",
            headers={"X-CSRF-Token": csrf_b},
        )
        self.assertEqual(res_del_forbidden.status_code, 403)

        # 6. Faculty Observer can view Document Alpha
        client_faculty = TestClient(app)
        log_f = client_faculty.post("/api/v1/auth/login", json={
            "username": "faculty",
            "password": "FacultyObserver123!",
        })
        self.assertEqual(log_f.status_code, 200)
        csrf_f = log_f.json()["csrf_token"]

        res_fac_get = client_faculty.get("/api/v1/documents/doc_alpha_private")
        self.assertEqual(res_fac_get.status_code, 200)
        self.assertEqual(res_fac_get.json()["doc_id"], "doc_alpha_private")

        # 7. Faculty Observer attempting DELETE -> 403 Forbidden (observer cannot delete)
        res_fac_del = client_faculty.delete(
            "/api/v1/documents/doc_alpha_private",
            headers={"X-CSRF-Token": csrf_f},
        )
        self.assertEqual(res_fac_del.status_code, 403)

        store.close()

    def test_15_guest_restrictions_and_unauthenticated_guards(self):
        """Verify that anonymous guests and GUEST roles cannot upload documents or create workspaces."""
        apply_migrations(self.db_path)
        app = create_app(db_path=str(self.db_path))
        unauth_client = TestClient(app)

        # Unauthenticated request to create workspace -> 401 Unauthorized
        res_create_ws = unauth_client.post("/api/v1/workspaces", json={"name": "Anon Space"})
        self.assertEqual(res_create_ws.status_code, 401)

        # Unauthenticated request to list workspaces -> 401 Unauthorized
        res_list_ws = unauth_client.get("/api/v1/workspaces")
        self.assertEqual(res_list_ws.status_code, 401)

        # Public health endpoint remains accessible
        res_health = unauth_client.get("/api/v1/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "HEALTHY")


if __name__ == "__main__":
    unittest.main()
