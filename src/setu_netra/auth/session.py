"""
session.py: Cryptographic session token generation, hashing, rotation, and cookie management.
"""

import datetime
import hashlib
import hmac
import secrets
from typing import Optional, Tuple
from fastapi import Response

SESSION_COOKIE_NAME = "setu_session"
CSRF_HEADER_NAME = "X-CSRF-Token"
DEFAULT_SESSION_DURATION_SECONDS = 86400  # 24 Hours


def generate_session_token() -> str:
    """Generate 256-bit cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 digest of session token for safe persistence."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_secret() -> str:
    """Generate cryptographically secure CSRF secret."""
    return secrets.token_hex(16)


def verify_csrf_token(header_token: Optional[str], session_secret: str) -> bool:
    """Verify CSRF token using constant-time comparison."""
    if not header_token or not session_secret:
        return False
    return hmac.compare_digest(header_token.strip(), session_secret.strip())


def set_session_cookie(
    response: Response,
    raw_token: str,
    max_age_seconds: int = DEFAULT_SESSION_DURATION_SECONDS,
    secure: bool = False,
    samesite: str = "lax",
) -> None:
    """Attach secure session cookie to HTTP response."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        path="/",
        httponly=True,
        secure=secure,
        samesite=samesite,
    )


def clear_session_cookie(response: Response, secure: bool = False, samesite: str = "lax") -> None:
    """Clear session cookie from client."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=secure,
        samesite=samesite,
    )
