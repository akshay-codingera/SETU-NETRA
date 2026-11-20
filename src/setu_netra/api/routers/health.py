"""
health.py: Health check and operational readiness endpoint (/api/v1/health).
"""

import logging
import urllib.request
import json
from fastapi import APIRouter, Depends

from setu_netra.api.dependencies import (
    get_doc_pipeline,
    get_inference_pipeline,
    get_uptime_seconds,
)
from setu_netra.api.schemas import HealthResponse
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.system_telemetry import get_system_telemetry

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)


def _check_ollama_daemon() -> dict:
    """Probe local Ollama daemon for operational connectivity."""
    url = "http://127.0.0.1:11434/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SetuNetra/2.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in body.get("models", [])]
                return {
                    "reachable": True,
                    "endpoint": "http://127.0.0.1:11434",
                    "installed_models": models,
                    "qwen_installed": any("qwen3.5:2b" in m for m in models),
                }
    except Exception as err:
        return {
            "reachable": False,
            "endpoint": "http://127.0.0.1:11434",
            "error": str(err),
            "installed_models": [],
            "qwen_installed": False,
        }
    return {"reachable": False, "endpoint": "http://127.0.0.1:11434", "installed_models": [], "qwen_installed": False}


@router.get("", response_model=HealthResponse)
async def get_health(
    doc_pipe: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    inf_pipe: IntelligentInferencePipeline = Depends(get_inference_pipeline),
) -> HealthResponse:
    """Return operational health, hardware headroom, and worker pool readiness."""
    
    # 1. Database check
    db_status = {"connected": False, "document_count": 0}
    try:
        docs = doc_pipe.store.list_documents()
        db_status["connected"] = True
        db_status["document_count"] = len(docs)
    except Exception as err:
        db_status["error"] = str(err)

    # 2. Ollama probe
    ollama_status = _check_ollama_daemon()

    # 3. Worker pool status
    pool_status = {}
    try:
        pool_obj = getattr(inf_pipe, "worker_pool", getattr(inf_pipe, "pool", None))
        if pool_obj:
            raw_pool = pool_obj.get_pool_status()
            pool_status = {
                "total_workers": len(raw_pool),
                "workers": {
                    wid: {
                        "model_id": getattr(w, "model_id", "unknown"),
                        "state": getattr(w, "state", "UNKNOWN"),
                        "queue_depth": getattr(w, "queue_depth", 0),
                        "active_requests": getattr(w, "active_requests", 0),
                    }
                    for wid, w in raw_pool.items()
                },
            }
    except Exception as err:
        pool_status["error"] = str(err)

    # 4. Hardware counters
    hardware_status = {}
    try:
        telemetry = get_system_telemetry()
        hardware_status = {
            "cpu_percent": getattr(telemetry, "cpu_percent", 0.0),
            "ram_total_mb": getattr(telemetry, "ram_total_mb", 0.0),
            "ram_used_mb": getattr(telemetry, "ram_used_mb", 0.0),
            "ram_free_mb": getattr(telemetry, "ram_free_mb", 0.0),
            "ram_percent": getattr(telemetry, "ram_percent", 0.0),
            "platform": getattr(telemetry, "platform", "windows"),
        }
    except Exception as err:
        hardware_status["error"] = str(err)

    # Composite health determination
    if not db_status.get("connected"):
        overall = "UNHEALTHY"
    elif not ollama_status.get("reachable"):
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return HealthResponse(
        status=overall,
        version="2.0.0-RC1",
        uptime_seconds=round(get_uptime_seconds(), 2),
        database=db_status,
        ollama=ollama_status,
        worker_pool=pool_status,
        hardware=hardware_status,
    )
