"""
roles.py: Role-Based Access Control (RBAC) definitions and capability matrices for SETU-NETRA.
"""

from enum import Enum
from typing import Dict, Set


class UserRole(str, Enum):
    """Discrete user privilege levels."""
    OWNER = "OWNER"
    RESEARCHER = "RESEARCHER"
    FACULTY_OBSERVER = "FACULTY_OBSERVER"
    GUEST = "GUEST"


class Permission(str, Enum):
    """Granular action permissions."""
    PLATFORM_ADMIN = "platform:admin"
    WORKSPACE_CREATE = "workspace:create"
    WORKSPACE_DELETE = "workspace:delete"
    WORKSPACE_MANAGE = "workspace:manage"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"
    QUERY_EXECUTE = "query:execute"
    QUERY_RESTRICTED = "query:execute_restricted"
    CONVERSATION_MANAGE = "conversation:manage"
    TELEMETRY_OBSERVE = "telemetry:observe"
    AUDIT_READ = "audit:read"
    REPORT_GENERATE = "report:generate"


# Complete RBAC Capability Matrix
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.OWNER: {
        Permission.PLATFORM_ADMIN,
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_DELETE,
        Permission.WORKSPACE_MANAGE,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE,
        Permission.QUERY_EXECUTE,
        Permission.QUERY_RESTRICTED,
        Permission.CONVERSATION_MANAGE,
        Permission.TELEMETRY_OBSERVE,
        Permission.AUDIT_READ,
        Permission.REPORT_GENERATE,
    },
    UserRole.RESEARCHER: {
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_MANAGE,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE,
        Permission.QUERY_EXECUTE,
        Permission.CONVERSATION_MANAGE,
        Permission.TELEMETRY_OBSERVE,
        Permission.REPORT_GENERATE,
    },
    UserRole.FACULTY_OBSERVER: {
        Permission.DOCUMENT_READ,
        Permission.QUERY_EXECUTE,
        Permission.TELEMETRY_OBSERVE,
        Permission.AUDIT_READ,
    },
    UserRole.GUEST: {
        Permission.DOCUMENT_READ,
        Permission.QUERY_RESTRICTED,
    },
}


def has_permission(role: UserRole | str, permission: Permission | str) -> bool:
    """Evaluate whether a role possesses a specific permission."""
    try:
        user_role = UserRole(role) if isinstance(role, str) else role
        perm = Permission(permission) if isinstance(permission, str) else permission
        return perm in ROLE_PERMISSIONS.get(user_role, set())
    except Exception:
        return False
