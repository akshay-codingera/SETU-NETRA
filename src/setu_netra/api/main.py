"""
main.py: FastAPI application entrypoint and ASGI server runner for SETU-NETRA V2.0.0-RC1.
"""

import argparse
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.api.dependencies import lifespan_manager
from setu_netra.api.errors import (
    SetuNetraException,
    http_exception_handler,
    setu_netra_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from setu_netra.api.middleware import CorrelationIdMiddleware
from setu_netra.api.routers import auth, documents, health, query, telemetry, workspaces

logger = logging.getLogger("setu_netra.api")


def create_app(db_path: str = "output/setu_netra.db") -> FastAPI:
    """Construct and configure the SETU-NETRA FastAPI application instance."""
    app = FastAPI(
        title="SETU-NETRA Kora Kaagaz Core API",
        description="Asynchronous Intelligent Document Understanding & Model Orchestration Engine",
        version="2.0.0-RC1",
        lifespan=lifespan_manager,
    )

    # Attach database path to app state
    app.state.db_path = db_path

    # 1. CORS Configuration (Restricted to local loopback origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8501",
            "http://127.0.0.1:8502",
            "http://localhost:8501",
            "http://localhost:8502",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    # 2. Correlation ID Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. RFC 9457 Problem Details Exception Handlers
    app.add_exception_handler(SetuNetraException, setu_netra_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 4. Include Routers under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(telemetry.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(auth.router)
    app.include_router(workspaces.router)
    app.include_router(documents.router)

    # 5. Presentation Layer / Static Files Mount
    dist_dir = Path("frontend/dist")
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend_assets")

    @app.get("/")
    async def root(request: Request):
        accept = request.headers.get("accept", "")
        if "text/html" in accept and dist_dir.exists() and (dist_dir / "index.html").exists():
            from fastapi.responses import FileResponse
            return FileResponse(dist_dir / "index.html")
        return {
            "name": "SETU-NETRA Kora Kaagaz Core API",
            "version": "2.0.0-RC1",
            "status": "OPERATIONAL",
            "docs_url": "/docs",
            "health_url": "/api/v1/health",
            "events_stream_url": "/api/v1/events/stream",
        }

    return app


def run_server(host: str = "127.0.0.1", port: int = 8502, db_path: str = "output/setu_netra.db") -> None:
    """Start Uvicorn ASGI server."""
    import uvicorn
    app = create_app(db_path=db_path)
    print(f"\n=======================================================")
    print(f"SETU-NETRA V2.0.0-RC1 (Kora Kaagaz Core ASGI)")
    print(f"Server running at: http://{host}:{port}/")
    print(f"Health endpoint:   http://{host}:{port}/api/v1/health")
    print(f"SSE Telemetry:     http://{host}:{port}/api/v1/events/stream")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SETU-NETRA ASGI Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8502, help="Port to listen on (default: 8502)")
    parser.add_argument("--db-path", type=str, default="output/setu_netra.db", help="Path to SQLite database")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, db_path=args.db_path)
