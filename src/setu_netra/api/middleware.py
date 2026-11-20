"""
middleware.py: Correlation ID tracking and propagation middleware for SETU-NETRA ASGI.
"""

import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable for thread/task-local correlation tracking
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="corr_unknown"
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware ensuring every HTTP request carries an X-Correlation-ID.
    If the client provides X-Correlation-ID, it is validated and preserved.
    Otherwise, a unique 'corr_<uuid4>' is assigned.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_corr_id = request.headers.get("X-Correlation-ID")
        if client_corr_id and client_corr_id.strip():
            correlation_id = client_corr_id.strip()
        else:
            correlation_id = f"corr_{uuid.uuid4().hex}"

        # Bind to contextvar and request state
        token = correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)


def get_current_correlation_id() -> str:
    """Retrieve the correlation ID of the active request context."""
    return correlation_id_ctx.get()
