"""
auth.py: Authentication and session management router for SETU-NETRA.
"""

from typing import Any, Dict, List, Optional
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from setu_netra.api.dependencies import (
    get_auth_service,
    get_current_session,
    require_authenticated,
    require_csrf,
)
from setu_netra.auth.rate_limiter import auth_rate_limiter
from setu_netra.auth.roles import Permission, UserRole, ROLE_PERMISSIONS
from setu_netra.auth.service import AuthService, AuthenticatedSession, UserRecord
from setu_netra.auth.session import (
    clear_session_cookie,
    set_session_cookie,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Security"])


def _is_request_secure(request: Request) -> bool:
    """Determine whether HTTPS transport is active."""
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or os.environ.get("SETU_HTTPS_ONLY", "false").lower() in ("true", "1")
    )


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="RESEARCHER")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    created_at: str
    updated_at: str


class SessionInfoResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None
    active_workspace_id: Optional[str] = None
    csrf_token: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


@router.post("/register", response_model=SessionInfoResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionInfoResponse:
    """Register a new user, issue Argon2id hash, allocate personal workspace, and set session cookie."""
    auth_rate_limiter.check(request)

    try:
        user = auth_service.register_user(
            username=req.username,
            password=req.password,
            display_name=req.display_name,
            role=req.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    raw_token, session_rec = auth_service.create_session(
        user_id=user.user_id,
        active_workspace_id=None,
    )
    is_secure = _is_request_secure(request)
    set_session_cookie(response, raw_token, secure=is_secure)

    perms = [p.value for p in ROLE_PERMISSIONS.get(user.role, set())]
    return SessionInfoResponse(
        authenticated=True,
        user=UserResponse(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        active_workspace_id=session_rec.active_workspace_id,
        csrf_token=session_rec.csrf_secret,
        permissions=perms,
    )


@router.post("/login", response_model=SessionInfoResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionInfoResponse:
    """Authenticate user with Argon2id, rotate prior active sessions, and issue fresh session cookie."""
    auth_rate_limiter.check(request)

    user, err = auth_service.authenticate_user(req.username, req.password)
    if not user or err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err or "Invalid username or password.",
        )

    raw_token, session_rec = auth_service.create_session(
        user_id=user.user_id,
        active_workspace_id=None,
    )
    is_secure = _is_request_secure(request)
    set_session_cookie(response, raw_token, secure=is_secure)

    perms = [p.value for p in ROLE_PERMISSIONS.get(user.role, set())]
    return SessionInfoResponse(
        authenticated=True,
        user=UserResponse(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        active_workspace_id=session_rec.active_workspace_id,
        csrf_token=session_rec.csrf_secret,
        permissions=perms,
    )


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(
    response: Response,
    auth_session: AuthenticatedSession = Depends(require_authenticated),
    auth_service: AuthService = Depends(get_auth_service),
) -> Dict[str, str]:
    """Revoke active session token in database and clear session cookie."""
    if auth_session.raw_token:
        auth_service.revoke_session(auth_session.raw_token)
    clear_session_cookie(response)
    return {"status": "logged_out", "message": "Session successfully terminated."}


@router.get("/session", response_model=SessionInfoResponse)
async def get_session_info(
    session: Optional[AuthenticatedSession] = Depends(get_current_session),
) -> SessionInfoResponse:
    """Return active user profile, workspace scope, CSRF token, and role capabilities."""
    if not session:
        return SessionInfoResponse(
            authenticated=False,
            user=None,
            active_workspace_id=None,
            csrf_token=None,
            permissions=[p.value for p in ROLE_PERMISSIONS.get(UserRole.GUEST, set())],
        )

    user = session.user
    perms = [p.value for p in ROLE_PERMISSIONS.get(user.role, set())]
    return SessionInfoResponse(
        authenticated=True,
        user=UserResponse(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        active_workspace_id=session.session.active_workspace_id,
        csrf_token=session.session.csrf_secret,
        permissions=perms,
    )
