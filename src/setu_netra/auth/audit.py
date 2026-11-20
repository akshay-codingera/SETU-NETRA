"""
audit.py: Tamper-evident cryptographic audit ledger implementing SHA-256 state chaining.

Security Notice:
In accordance with systems engineering reality, SHA-256 hash chaining provides TAMPER-EVIDENCE
(retroactive alteration of records breaks downstream hashes). It does NOT automatically provide
absolute immutability against an attacker possessing raw administrative physical write access
to the SQLite file who could recalculate the chain. For external immutability, periodic chain
hashes must be exported to external faculty observers.
"""

import datetime
import hashlib
import json
import logging
import sqlite3
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Sensitive keywords strictly forbidden from entering audit log records
REDACT_KEYS = {"password", "token", "secret", "api_key", "authorization", "csrf", "cookie", "content", "file_bytes"}


def sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively scrub credentials and private payload contents from audit logs."""
    sanitized = {}
    for k, v in details.items():
        if any(bad in k.lower() for bad in REDACT_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_details(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            # Truncate any long strings to prevent accidental leakage of raw text
            if isinstance(v, str) and len(v) > 256:
                sanitized[k] = v[:256] + "...[TRUNCATED]"
            else:
                sanitized[k] = v
        else:
            sanitized[k] = str(v)
    return sanitized


class AuditLedger:
    """Manages immutable audit log entries using SHA-256 state chaining."""

    @staticmethod
    def log_event(
        conn: sqlite3.Connection,
        action: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record an audit event with SHA-256 cryptographic linkage to the preceding record.
        Returns the computed entry_hash.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_details = sanitize_details(details or {})
        details_json = json.dumps(clean_details, sort_keys=True)

        with conn:
            # 1. Fetch hash of latest preceding record
            cursor = conn.execute("SELECT entry_hash FROM audit_ledger ORDER BY entry_id DESC LIMIT 1;")
            row = cursor.fetchone()
            prev_hash = row[0] if row else "0" * 64

            # 2. Compute SHA-256 hash chaining
            payload_str = f"{prev_hash}|{now_iso}|{action}|{user_id or ''}|{workspace_id or ''}|{details_json}"
            entry_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            # 3. Store record
            conn.execute(
                """
                INSERT INTO audit_ledger (prev_hash, entry_hash, action, user_id, workspace_id, timestamp_iso, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (prev_hash, entry_hash, action, user_id, workspace_id, now_iso, details_json),
            )

        logger.info(f"Audit event logged: {action} (User: {user_id}, WS: {workspace_id}, Hash: {entry_hash[:12]}...)")
        return entry_hash

    @staticmethod
    def verify_chain_integrity(conn: sqlite3.Connection) -> Tuple[bool, Optional[int]]:
        """
        Traverse the entire audit chain from inception to present, verifying cryptographic continuity.
        Returns (True, None) if completely valid, or (False, corrupted_entry_id) if tampering is detected.
        """
        cursor = conn.execute("SELECT entry_id, prev_hash, entry_hash, action, user_id, workspace_id, timestamp_iso, details_json FROM audit_ledger ORDER BY entry_id ASC;")
        rows = cursor.fetchall()

        if not rows:
            return True, None

        expected_prev = "0" * 64
        for row in rows:
            eid, prev_hash, entry_hash, action, uid, wid, ts, det = (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
            )

            # Check previous hash continuity
            if prev_hash != expected_prev:
                logger.error(f"Audit chain broken at entry_id={eid}: expected prev_hash={expected_prev}, found={prev_hash}")
                return False, eid

            # Recompute entry hash
            payload_str = f"{prev_hash}|{ts}|{action}|{uid or ''}|{wid or ''}|{det}"
            computed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            if computed_hash != entry_hash:
                logger.error(f"Audit hash mismatch at entry_id={eid}: computed={computed_hash}, stored={entry_hash}")
                return False, eid

            expected_prev = entry_hash

        return True, None
