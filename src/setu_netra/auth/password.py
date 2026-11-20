"""
password.py: Argon2id password hashing and cryptographic verification conforming to RFC 9106.
"""

import logging
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

logger = logging.getLogger(__name__)

# Argon2id parameters (RFC 9106 recommended profile for high-security services)
# Memory cost: 64 MB (65536 KiB), Time cost: 3 iterations, Parallelism: 4 lanes
_HASHER = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID,
)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id with cryptographically random salt."""
    if not plain_password or len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters in length.")
    return _HASHER.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash with constant-time equality."""
    if not plain_password or not password_hash:
        return False
    try:
        return _HASHER.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as err:
        logger.error(f"Unexpected error during Argon2id verification: {err}")
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check if the password hash needs to be updated to match current parameters."""
    try:
        return _HASHER.check_needs_rehash(password_hash)
    except Exception:
        return True
