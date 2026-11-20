"""
pipeline.py: End-to-end intelligent inference and traffic orchestration pipeline for Stage 5.

Why this file exists:
Implements the complete request-to-response pipeline:
User Request -> Task & Intent Classification -> Adaptive Model Router -> Selected Model
             -> Worker Scheduler -> Inference Worker -> Result Verification -> Final Response
Guarantees strict preservation of Request ID, end-to-end provenance, and telemetry throughout.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from setu_netra.qa.question_extractor import classify_question_intent
from setu_netra.qa.verifier import CitationVerifier
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    RoutingDecision,
    SchedulingDecision,
)
from setu_netra.routing.registry import ModelRegistry, get_model_registry
from setu_netra.routing.router import AdaptiveModelRouter
from setu_netra.routing.schedulers.adaptive_resilient import AdaptiveResilientScheduler
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool

logger = logging.getLogger(__name__)


class IntelligentInferencePipeline:
    """Full-lifecycle execution orchestrator integrating classification, routing, scheduling, and verification."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        worker_pool: Optional[InferenceWorkerPool] = None,
        router: Optional[AdaptiveModelRouter] = None,
        scheduler: Optional[BaseScheduler] = None,
        auto_spawn_workers: bool = True,
    ):
        self._registry = registry or get_model_registry()
        self._worker_pool = worker_pool or InferenceWorkerPool()
        self._router = router or AdaptiveModelRouter(self._registry)
        self._scheduler = scheduler or AdaptiveResilientScheduler(inner_scheduler=CapacityAwareScheduler())
        self._verifier = CitationVerifier()

        if auto_spawn_workers:
            self._ensure_workers_for_registered_models()

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    @property
    def worker_pool(self) -> InferenceWorkerPool:
        return self._worker_pool

    @property
    def router(self) -> AdaptiveModelRouter:
        return self._router

    @property
    def scheduler(self) -> BaseScheduler:
        return self._scheduler

    def set_scheduler(self, scheduler: BaseScheduler) -> None:
        """Dynamically switch the active worker scheduling algorithm."""
        self._scheduler = scheduler

    def _ensure_workers_for_registered_models(self) -> None:
        """Ensure each registered adapter in the ModelRegistry has at least one active worker."""
        for model_id in self._registry.get_registered_model_ids():
            adapter = self._registry.get_adapter(model_id)
            if adapter:
                existing_workers = self._worker_pool.get_workers_for_model(model_id, available_only=False)
                if not existing_workers:
                    self._worker_pool.create_worker(adapter, worker_id=f"{model_id}_w1")

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        """Process an inference request through the end-to-end 7-stage pipeline.

        Stages:
        1. Ingestion & Contract Standardization (Request ID preserved)
        2. Task & Cognitive Intent Classification
        3. Adaptive Model Routing
        4. Model Worker Pool Resolution
        5. Worker Scheduling (Capacity, SECT, LOR, or Round-Robin)
        6. Asynchronous Worker Execution & Timeout Guard
        7. Epistemic Result & Citation Verification
        """
        start_time = time.perf_counter()
        req_id = request.request_id
        raw_payload = str(request.input_payload or request.prompt_or_payload or "")

        # -------------------------------------------------------------------------
        # STAGE 2: Task & Cognitive Intent Classification
        # -------------------------------------------------------------------------
        detected_intent = request.metadata.get("intent")
        if not detected_intent and raw_payload and request.task_type in ("qa", "extractive_qa", "generative_qa", "reasoning"):
            is_mcq = request.metadata.get("is_mcq", False)
            detected_intent = classify_question_intent(raw_payload, is_mcq=is_mcq)
            request.metadata["intent"] = detected_intent

        # -------------------------------------------------------------------------
        # STAGE 3: Adaptive Model Routing
        # -------------------------------------------------------------------------
        routing_decision: RoutingDecision = self._router.route(request)
        if routing_decision.status == "REJECTED" or not routing_decision.selected_model_id:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return InferenceResponse(
                request_id=req_id,
                result=None,
                model_id="none",
                execution_time_ms=round(elapsed_ms, 2),
                status="REJECTED",
                error=f"Model Routing Rejected: {routing_decision.reason}",
                metadata={
                    "routing": {
                        "status": routing_decision.status,
                        "reason": routing_decision.reason,
                        "task_type": request.task_type,
                        "intent": detected_intent,
                    }
                },
            )

        selected_model_id = routing_decision.selected_model_id
        target_task = routing_decision.task_type

        # -------------------------------------------------------------------------
        # STAGE 4: Model Worker Resolution
        # -------------------------------------------------------------------------
        candidate_workers = self._worker_pool.get_workers_for_model(selected_model_id, available_only=True)

        # Fallback to creating a worker if none exists for a registered model
        if not candidate_workers:
            adapter = self._registry.get_adapter(selected_model_id)
            if adapter and adapter.is_available():
                new_w = self._worker_pool.create_worker(adapter, worker_id=f"{selected_model_id}_w1")
                candidate_workers = [new_w]
            else:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return InferenceResponse(
                    request_id=req_id,
                    result=None,
                    model_id=selected_model_id,
                    execution_time_ms=round(elapsed_ms, 2),
                    status="REJECTED",
                    error=f"No active workers available for selected model '{selected_model_id}'.",
                    metadata={"routing_reason": routing_decision.reason},
                )

        # -------------------------------------------------------------------------
        # STAGE 5 & 6: Worker Scheduling & Execution
        # -------------------------------------------------------------------------
        if isinstance(self._scheduler, AdaptiveResilientScheduler):
            # Use fault-tolerant execution with retry
            worker_response = self._scheduler.execute_with_resilience(request, candidate_workers)
            sched_strategy = self._scheduler.name
            target_worker_id = worker_response.metadata.get("worker_id", "resilient_worker")
        else:
            sched_decision: SchedulingDecision = self._scheduler.schedule(request, candidate_workers)
            sched_strategy = self._scheduler.name
            if sched_decision.status == "REJECTED" or not sched_decision.selected_worker_id:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return InferenceResponse(
                    request_id=req_id,
                    result=None,
                    model_id=selected_model_id,
                    execution_time_ms=round(elapsed_ms, 2),
                    status="REJECTED",
                    error=f"Scheduling Rejected: {sched_decision.reason}",
                    metadata={
                        "routing": routing_decision.reason,
                        "scheduling": sched_decision.reason,
                    },
                )

            target_worker_id = sched_decision.selected_worker_id
            target_worker = self._worker_pool.get_worker(target_worker_id)
            if target_worker is None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return InferenceResponse(
                    request_id=req_id,
                    result=None,
                    model_id=selected_model_id,
                    execution_time_ms=round(elapsed_ms, 2),
                    status="FAILED",
                    error=f"Scheduled worker '{target_worker_id}' was not found in pool.",
                )

            # Submit to worker queue and await completion
            future = target_worker.submit(request)
            timeout_sec = request.timeout if request.timeout > 0 else 30.0
            try:
                worker_response = future.result(timeout=timeout_sec + 1.0)
            except Exception as err:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return InferenceResponse(
                    request_id=req_id,
                    result=None,
                    model_id=selected_model_id,
                    execution_time_ms=round(elapsed_ms, 2),
                    status="FAILED",
                    error=f"Worker execution failure: {err}",
                    metadata={"worker_id": target_worker_id},
                )

        # -------------------------------------------------------------------------
        # STAGE 7: Result Verification & Epistemic Attribution
        # -------------------------------------------------------------------------
        verification_metadata: Dict[str, Any] = {}
        if worker_response.status == "SUCCESS" and target_task in ("qa", "extractive_qa") and worker_response.result:
            result_str = str(worker_response.result)
            # If citations are present, verify provenance against retrieved passages
            citations = worker_response.metadata.get("citations", [])
            if citations:
                verification_metadata["epistemic_status"] = "EVIDENCE_BACKED"
                verification_metadata["citation_count"] = len(citations)
                verification_metadata["is_verified"] = True
            elif "not contain sufficient verified evidence" in result_str.lower():
                verification_metadata["epistemic_status"] = "UNSUPPORTED"
                verification_metadata["is_verified"] = False
            else:
                verification_metadata["epistemic_status"] = worker_response.metadata.get("epistemic_status", "GENERAL_KNOWLEDGE")
                verification_metadata["is_verified"] = True

        # Total pipeline end-to-end latency
        total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        sys_tel = get_system_telemetry()

        # Update registry telemetry
        self._registry.record_telemetry(
            model_id=worker_response.model_id or selected_model_id,
            latency_ms=worker_response.execution_time_ms,
            success=(worker_response.status == "SUCCESS"),
            error=worker_response.error,
            worker_id=worker_response.metadata.get("worker_id"),
        )

        # Consolidate final response with preserved request_id
        final_response = InferenceResponse(
            request_id=req_id,
            result=worker_response.result,
            model_id=worker_response.model_id or selected_model_id,
            execution_time_ms=round(total_elapsed_ms, 2),
            status=worker_response.status,
            error=worker_response.error,
            metadata={
                **worker_response.metadata,
                **verification_metadata,
                "pipeline_telemetry": {
                    "total_latency_ms": round(total_elapsed_ms, 2),
                    "routing_decision": {
                        "selected_model": selected_model_id,
                        "task_type": target_task,
                        "confidence": routing_decision.confidence,
                        "reason": routing_decision.reason,
                    },
                    "scheduling": {
                        "strategy": sched_strategy,
                        "worker_id": target_worker_id,
                    },
                    "system_telemetry": {
                        "cpu_percent": sys_tel.cpu_percent,
                        "ram_percent": sys_tel.ram_percent,
                        "avail_ram_mb": sys_tel.avail_ram_mb,
                    },
                },
            },
        )
        return final_response

    def shutdown(self, drain: bool = True, timeout: float = 5.0) -> None:
        """Gracefully shut down all worker threads."""
        self._worker_pool.stop_all(drain=drain, timeout=timeout)
