"""
workspaces.py: Workspace desk management and isolation router for SETU-NETRA.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from setu_netra.api.dependencies import (
    get_auth_service,
    require_authenticated,
    require_csrf,
    require_permission,
)
from setu_netra.auth.roles import Permission, UserRole
from setu_netra.auth.service import AuthService, AuthenticatedSession, WorkspaceRecord

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces Desk"])


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: str
    owner_id: str
    created_at: str
    updated_at: str
    is_active: bool = False


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    session: AuthenticatedSession = Depends(require_authenticated),
    auth_service: AuthService = Depends(get_auth_service),
) -> List[WorkspaceResponse]:
    """List all workspaces accessible to the authenticated user."""
    workspaces = auth_service.get_user_workspaces(session.user.user_id, session.user.role)
    active_ws = session.session.active_workspace_id
    return [
        WorkspaceResponse(
            workspace_id=w.workspace_id,
            name=w.name,
            description=w.description,
            owner_id=w.owner_id,
            created_at=w.created_at,
            updated_at=w.updated_at,
            is_active=(w.workspace_id == active_ws),
        )
        for w in workspaces
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def create_workspace(
    req: CreateWorkspaceRequest,
    session: AuthenticatedSession = Depends(require_authenticated),
    auth_service: AuthService = Depends(get_auth_service),
) -> WorkspaceResponse:
    """Create a new isolated workspace namespace bound to the user."""
    # Enforce permission
    from setu_netra.auth.roles import has_permission
    if not has_permission(session.user.role, Permission.WORKSPACE_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current role is not authorized to create workspaces.",
        )

    try:
        ws = auth_service.create_workspace(
            name=req.name,
            description=req.description,
            owner_id=session.user.user_id,
        )
        return WorkspaceResponse(
            workspace_id=ws.workspace_id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            is_active=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    session: AuthenticatedSession = Depends(require_authenticated),
    auth_service: AuthService = Depends(get_auth_service),
) -> WorkspaceResponse:
    """Retrieve details for a specific workspace with boundary verification."""
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=workspace_id,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to workspace '{workspace_id}'.",
        )

    workspaces = auth_service.get_user_workspaces(session.user.user_id, session.user.role)
    ws = next((w for w in workspaces if w.workspace_id == workspace_id), None)
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    return WorkspaceResponse(
        workspace_id=ws.workspace_id,
        name=ws.name,
        description=ws.description,
        owner_id=ws.owner_id,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        is_active=(ws.workspace_id == session.session.active_workspace_id),
    )


@router.post("/{workspace_id}/switch", dependencies=[Depends(require_csrf)])
async def switch_workspace(
    workspace_id: str,
    session: AuthenticatedSession = Depends(require_authenticated),
    auth_service: AuthService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """Switch the active workspace for the current session."""
    success = auth_service.switch_active_workspace(
        session_id_hash=session.session.session_id_hash,
        user_id=session.user.user_id,
        role=session.user.role,
        new_workspace_id=workspace_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot switch to workspace '{workspace_id}': access denied or workspace does not exist.",
        )
    return {"status": "success", "active_workspace_id": workspace_id}
