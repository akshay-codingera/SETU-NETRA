"""
errors.py: RFC 9457 Problem Details for HTTP APIs error handling and custom exceptions.
"""

import datetime
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from setu_netra.api.middleware import get_current_correlation_id
from setu_netra.api.schemas import ProblemDetails


class SetuNetraException(Exception):
    """Base application exception supporting RFC 9457 Problem Details attributes."""

    def __init__(
        self,
        status_code: int = 500,
        title: str = "Internal System Error",
        detail: Optional[str] = None,
        code: Optional[str] = "ERR_INTERNAL",
        type_uri: str = "https://setu-netra.internal/errors/INTERNAL_ERROR",
    ):
        super().__init__(detail or title)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.code = code
        self.type_uri = type_uri


class InsufficientMemoryException(SetuNetraException):
    """Raised when host memory headroom is below model execution safety threshold."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=503,
            title="Insufficient Hardware Memory Headroom",
            detail=detail,
            code="ERR_INSUFFICIENT_MEMORY",
            type_uri="https://setu-netra.internal/errors/INSUFFICIENT_MEMORY",
        )


class ModelBusyException(SetuNetraException):
    """Raised when model concurrency ceiling is saturated and queue is at capacity."""

    def __init__(self, detail: str = "Model worker concurrency limit reached."):
        super().__init__(
            status_code=429,
            title="Model Execution Concurrency Saturated",
            detail=detail,
            code="ERR_MODEL_BUSY",
            type_uri="https://setu-netra.internal/errors/MODEL_BUSY",
        )


class ResourceNotFoundException(SetuNetraException):
    """Raised when requested document, block, or entity is not found."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=404,
            title="Resource Not Found",
            detail=detail,
            code="ERR_NOT_FOUND",
            type_uri="https://setu-netra.internal/errors/NOT_FOUND",
        )


class ValidationException(SetuNetraException):
    """Raised when request payload fails semantic domain validation."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=400,
            title="Invalid Request Parameters",
            detail=detail,
            code="ERR_INVALID_PARAMS",
            type_uri="https://setu-netra.internal/errors/INVALID_PARAMS",
        )


def _get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or get_current_correlation_id()


async def setu_netra_exception_handler(request: Request, exc: SetuNetraException) -> JSONResponse:
    """Handler for application domain exceptions returning RFC 9457 JSON."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    problem = ProblemDetails(
        type=exc.type_uri,
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
        correlation_id=_get_correlation_id(request),
        timestamp=now_iso,
        code=exc.code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content=problem.model_dump(),
        headers={"X-Correlation-ID": problem.correlation_id or ""},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for Pydantic/FastAPI validation errors returning RFC 9457 JSON."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    invalid_params = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        invalid_params.append({
            "name": loc,
            "reason": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        })

    problem = ProblemDetails(
        type="https://setu-netra.internal/errors/VALIDATION_ERROR",
        title="Unprocessable Entity",
        status=422,
        detail="The request body or query parameters failed schema validation.",
        instance=str(request.url.path),
        correlation_id=_get_correlation_id(request),
        timestamp=now_iso,
        code="ERR_VALIDATION",
        invalid_params=invalid_params,
    )
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content=problem.model_dump(),
        headers={"X-Correlation-ID": problem.correlation_id or ""},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for standard Starlette/FastAPI HTTPExceptions returning RFC 9457 JSON."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    problem = ProblemDetails(
        type="https://setu-netra.internal/errors/HTTP_ERROR",
        title=exc.detail if isinstance(exc.detail, str) else "HTTP Request Error",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url.path),
        correlation_id=_get_correlation_id(request),
        timestamp=now_iso,
        code=f"ERR_HTTP_{exc.status_code}",
    )
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content=problem.model_dump(),
        headers={"X-Correlation-ID": problem.correlation_id or ""},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected server exceptions returning RFC 9457 JSON."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    problem = ProblemDetails(
        type="https://setu-netra.internal/errors/UNHANDLED_EXCEPTION",
        title="Internal Server Error",
        status=500,
        detail=str(exc) or "An unexpected internal server error occurred.",
        instance=str(request.url.path),
        correlation_id=_get_correlation_id(request),
        timestamp=now_iso,
        code="ERR_UNHANDLED",
    )
    return JSONResponse(
        status_code=500,
        media_type="application/problem+json",
        content=problem.model_dump(),
        headers={"X-Correlation-ID": problem.correlation_id or ""},
    )
