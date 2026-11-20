"""
pipeline_adapter.py: Non-blocking asynchronous adapter for SETU-NETRA InferencePipeline.
Dispatches synchronous pipeline execution via anyio.to_thread.run_sync with a bounded
CapacityLimiter, preserving model concurrency semaphores and publishing real-time telemetry.
"""

import anyio
import anyio.to_thread
import logging
from typing import Any, Dict, Optional

from setu_netra.api.event_bus import EventBus
from setu_netra.qa.engine import EvidenceGroundedQAEngine, VerifiedAnswer
from setu_netra.routing.pipeline import IntelligentInferencePipeline

logger = logging.getLogger(__name__)


class AsyncPipelineAdapter:
    """
    Asynchronous, non-blocking bridge wrapping EvidenceGroundedQAEngine and
    IntelligentInferencePipeline.
    
    Architectural Guarantees:
    - Bounded Thread Execution: Uses anyio.to_thread.run_sync with an explicit CapacityLimiter.
    - Zero Event Loop Blocking: Heavy CPU inference yields to the ASGI loop.
    - Concurrency Preservation: Preserves internal adapter locks (e.g. Ollama 1-concurrency).
    - Provenance & Telemetry: Emits genuine lifecycle events to the EventBus.
    """

    def __init__(
        self,
        qa_engine: EvidenceGroundedQAEngine,
        inference_pipeline: IntelligentInferencePipeline,
        event_bus: EventBus,
        max_concurrent_threads: int = 4,
    ):
        self.qa_engine = qa_engine
        self.inference_pipeline = inference_pipeline
        self.event_bus = event_bus
        self.capacity_limiter = anyio.CapacityLimiter(total_tokens=max_concurrent_threads)

    async def answer_question(
        self,
        query: str,
        doc_id: Optional[str] = None,
        model_id: Optional[str] = None,
        think: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.20,
        correlation_id: str = "corr_default",
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute question answering inside a bounded thread pool without blocking ASGI loop."""
        
        # 1. Publish ingress lifecycle event
        self.event_bus.publish(
            event_type="REQUEST_INGRESS",
            source_subsystem="AsyncPipelineAdapter",
            payload={
                "query": query,
                "doc_id": doc_id,
                "requested_model_id": model_id,
                "top_k": top_k,
                "threshold": threshold,
                "workspace_id": workspace_id,
            },
            correlation_id=correlation_id,
        )

        think_bool: Optional[bool] = None
        if think is not None:
            if isinstance(think, bool):
                think_bool = think
            elif isinstance(think, str):
                think_bool = think.lower() in ("true", "1", "keep", "yes")

        def _sync_execute() -> VerifiedAnswer:
            return self.qa_engine.answer_question(
                query=query,
                doc_id=doc_id,
                top_k=top_k,
                threshold=threshold,
                model_id=model_id,
                think=think_bool,
                workspace_id=workspace_id,
            )

        # 2. Dispatch to bounded thread pool
        try:
            answer: VerifiedAnswer = await anyio.to_thread.run_sync(
                _sync_execute,
                limiter=self.capacity_limiter,
            )
        except Exception as err:
            logger.error(f"Error during async pipeline execution: {err}")
            self.event_bus.publish(
                event_type="REQUEST_FAILED",
                source_subsystem="AsyncPipelineAdapter",
                payload={"error": str(err)},
                correlation_id=correlation_id,
            )
            raise

        resp_meta = answer.metadata or {}
        thinking_trace = resp_meta.get("thinking") or resp_meta.get("pipeline_telemetry", {}).get("thinking")
        worker_id = resp_meta.get("worker_id", "default_worker")

        # 3. Publish verifier & egress lifecycle events
        self.event_bus.publish(
            event_type="VERIFIER_TAXONOMY",
            source_subsystem="CitationVerifier",
            payload={
                "epistemic_status": answer.epistemic_status,
                "grounding_score": answer.grounding_score,
                "citations_count": len(answer.citations),
                "model_id": answer.executing_model_id,
                "worker_id": worker_id,
            },
            correlation_id=correlation_id,
        )

        self.event_bus.publish(
            event_type="EGRESS_COMPLETED",
            source_subsystem="AsyncPipelineAdapter",
            payload={
                "execution_time_ms": answer.execution_time_ms,
                "executing_model_id": answer.executing_model_id,
                "worker_id": worker_id,
            },
            correlation_id=correlation_id,
        )

        return {
            "query": answer.query,
            "answer_text": answer.answer_text,
            "epistemic_status": answer.epistemic_status,
            "citations": answer.citations,
            "grounding_score": answer.grounding_score,
            "executing_model_id": answer.executing_model_id,
            "executing_worker_id": worker_id,
            "execution_time_ms": answer.execution_time_ms,
            "explanation": answer.explanation,
            "thinking": thinking_trace,
            "correlation_id": correlation_id,
            "pipeline_telemetry": resp_meta.get("pipeline_telemetry", {}),
            "domain": getattr(answer, "domain", "DOCUMENT_QA"),
            "reconstructed_question": getattr(answer, "reconstructed_question", None),
            "verification_method": getattr(answer, "verification_method", None),
            "step_by_step_explanation": getattr(answer, "step_by_step_explanation", None),
            "options": resp_meta.get("options", []),
            "selected_option": resp_meta.get("selected_option"),
            "option_analysis": resp_meta.get("option_analysis", {}),
        }
