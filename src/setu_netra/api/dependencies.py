"""
dependencies.py: Subsystem dependency injection and ASGI lifespan management for SETU-NETRA.
"""

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional, Sequence

from fastapi import Depends, FastAPI, HTTPException, Request, status

from setu_netra.api.event_bus import EventBus, get_event_bus
from setu_netra.api.pipeline_adapter import AsyncPipelineAdapter
from setu_netra.auth.roles import Permission, UserRole, has_permission
from setu_netra.auth.service import AuthService, AuthenticatedSession, UserRecord
from setu_netra.auth.session import SESSION_COOKIE_NAME
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.engine import EvidenceGroundedQAEngine
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import get_model_registry
from setu_netra.store.migrations import apply_migrations

logger = logging.getLogger(__name__)

# Global runtime state singletons
_doc_pipeline: Optional[DocumentIntelligencePipeline] = None
_inference_pipeline: Optional[IntelligentInferencePipeline] = None
_qa_engine: Optional[EvidenceGroundedQAEngine] = None
_pipeline_adapter: Optional[AsyncPipelineAdapter] = None
_auth_service: Optional[AuthService] = None
_app_start_time: float = 0.0
_active_db_path: str = "output/setu_netra.db"


def init_subsystems(db_path: str = "output/setu_netra.db") -> None:
    """Initialize core SETU-NETRA subsystems, database migrations, and async pipeline adapter."""
    global _doc_pipeline, _inference_pipeline, _qa_engine, _pipeline_adapter, _auth_service, _app_start_time, _active_db_path
    
    _app_start_time = time.time()
    _active_db_path = db_path
    
    # 0. Apply database migrations non-destructively
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    try:
        apply_migrations(db_path)
    except Exception as e:
        logger.warning(f"Database migration notice during startup: {e}")

    # 1. Document pipeline and store
    _doc_pipeline = DocumentIntelligencePipeline(db_path=db_path)

    # 2. Auth & RBAC service
    _auth_service = AuthService(db_path=db_path)

    # 3. Registry & Inference pipeline
    registry = get_model_registry()
    _inference_pipeline = IntelligentInferencePipeline(
        registry=registry,
        auto_spawn_workers=True,
    )

    # 4. Grounded QA Engine
    _qa_engine = EvidenceGroundedQAEngine(
        retriever=_doc_pipeline.retriever,
        inference_pipeline=_inference_pipeline,
    )

    # 5. Async non-blocking adapter
    event_bus = get_event_bus()
    _pipeline_adapter = AsyncPipelineAdapter(
        qa_engine=_qa_engine,
        inference_pipeline=_inference_pipeline,
        event_bus=event_bus,
        max_concurrent_threads=4,
    )

    logger.info("SETU-NETRA core subsystems initialized successfully.")


def shutdown_subsystems() -> None:
    """Cleanly teardown subsystems and background workers."""
    global _doc_pipeline, _inference_pipeline, _pipeline_adapter
    event_bus = get_event_bus()
    event_bus.stop()
    
    if _inference_pipeline and hasattr(_inference_pipeline, "pool"):
        try:
            _inference_pipeline.pool.shutdown()
        except Exception as e:
            logger.warning(f"Error shutting down worker pool: {e}")

    logger.info("SETU-NETRA subsystems shut down cleanly.")


@asynccontextmanager
async def lifespan_manager(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI ASGI lifespan managing startup and graceful shutdown."""
    loop = asyncio.get_running_loop()
    event_bus = get_event_bus()
    event_bus.bind_loop(loop)
    event_bus.start_heartbeat(interval_seconds=15.0)

    # Initialize subsystems if not already configured
    db_path = getattr(app.state, "db_path", "output/setu_netra.db")
    if _pipeline_adapter is None:
        init_subsystems(db_path=db_path)

    logger.info("ASGI Lifespan: Server started and event bus active.")
    try:
        yield
    finally:
        shutdown_subsystems()
        logger.info("ASGI Lifespan: Server stopped.")


def get_pipeline_adapter(request: Request) -> AsyncPipelineAdapter:
    """Dependency provider for AsyncPipelineAdapter."""
    global _pipeline_adapter, _active_db_path
    db_path = getattr(request.app.state, "db_path", _active_db_path)
    if _pipeline_adapter is None or _active_db_path != db_path:
        init_subsystems(db_path=db_path)
    assert _pipeline_adapter is not None
    return _pipeline_adapter


def get_inference_pipeline() -> IntelligentInferencePipeline:
    """Dependency provider for IntelligentInferencePipeline."""
    if _inference_pipeline is None:
        init_subsystems()
    assert _inference_pipeline is not None
    return _inference_pipeline


def get_doc_pipeline(request: Request) -> DocumentIntelligencePipeline:
    """Dependency provider for DocumentIntelligencePipeline."""
    global _doc_pipeline, _active_db_path
    db_path = getattr(request.app.state, "db_path", _active_db_path)
    if _doc_pipeline is None or str(_doc_pipeline.store.db_path) != str(Path(db_path)):
        _doc_pipeline = DocumentIntelligencePipeline(db_path=db_path)
    return _doc_pipeline


def get_uptime_seconds() -> float:
    """Return application uptime in seconds."""
    if _app_start_time == 0.0:
        return 0.0
    return time.time() - _app_start_time


def get_auth_service(request: Request) -> AuthService:
    """Dependency provider for AuthService dynamically bound to request app db_path."""
    global _active_db_path
    db_path = getattr(request.app.state, "db_path", _active_db_path)
    return AuthService(db_path=db_path)


def get_current_session(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[AuthenticatedSession]:
    """Extract and validate active session from HttpOnly cookie or Authorization Bearer header."""
    # 1. Try HttpOnly session cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)
    
    # 2. Fallback to Authorization: Bearer <token>
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        return None

    return auth_service.get_session_by_token(token)


def get_current_user(
    session: Optional[AuthenticatedSession] = Depends(get_current_session),
) -> UserRecord:
    """Resolve current user record; defaults to anonymous GUEST if unauthenticated."""
    if session is not None:
        return session.user
    return UserRecord(
        user_id="guest_anon",
        username="guest",
        display_name="Guest User",
        role=UserRole.GUEST,
        created_at="",
        updated_at="",
    )


def require_authenticated(
    session: Optional[AuthenticatedSession] = Depends(get_current_session),
) -> AuthenticatedSession:
    """Enforce that the requesting client has an active, valid session."""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )
    return session


def require_csrf(
    request: Request,
    session: AuthenticatedSession = Depends(require_authenticated),
) -> None:
    """Verify anti-CSRF token on state-changing HTTP requests."""
    csrf_token = request.headers.get("X-CSRF-Token", "")
    if not csrf_token or not secrets.compare_digest(csrf_token, session.session.csrf_secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token (X-CSRF-Token).",
        )


def require_permission(permission: Permission) -> Callable:
    """Dependency factory checking whether the current user's role has the requested permission."""
    def dependency(user: UserRecord = Depends(get_current_user)) -> UserRecord:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' does not possess required permission '{permission.value}'.",
            )
        return user
    return dependency


def require_role(*roles: UserRole) -> Callable:
    """Dependency factory checking whether the current user is among allowed roles."""
    def dependency(user: UserRecord = Depends(get_current_user)) -> UserRecord:
        if user.role not in roles:
            allowed = [r.value for r in roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user.role.value}' is not authorized. Required: {allowed}",
            )
        return user
    return dependency
