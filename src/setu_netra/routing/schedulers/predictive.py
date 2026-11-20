"""
predictive.py: Shortest Estimated Completion Time (SECT) predictive traffic scheduler.

Why this file exists:
Predicts total completion time (queue waiting time + execution service time) for each worker:
ECT(w, r) = WaitTime(w) + ExecTime(w, r)
Using Exponentially Weighted Moving Average (EWMA) latency and request token complexity.
"""

from typing import List, Optional

from setu_netra.routing.contracts import InferenceRequest
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.worker_pool import InferenceWorker


class ShortestEstimatedCompletionTimeScheduler(BaseScheduler):
    """Predictive scheduler dispatching to the worker with minimum estimated total completion time."""

    def __init__(self, default_service_time_ms: float = 50.0):
        self._default_service_time_ms = default_service_time_ms

    @property
    def name(self) -> str:
        return "SECT"

    def _estimate_service_time(self, worker: InferenceWorker, request: InferenceRequest) -> float:
        """Estimate execution latency for this specific request on the worker."""
        # 1. Base latency from worker's EWMA, or adapter metadata, or default
        if worker.ewma_latency_ms is not None:
            base_ms = worker.ewma_latency_ms
        else:
            meta = worker.adapter.metadata
            if meta and meta.measured_latency and "mean_ms" in meta.measured_latency:
                base_ms = meta.measured_latency["mean_ms"]
            else:
                # Heuristic defaults based on model category
                cat = meta.model_type if meta else ""
                if "Generative" in cat:
                    base_ms = 2500.0
                elif "Extractive" in cat:
                    base_ms = 2.0
                elif "Classification" in cat:
                    base_ms = 1.0
                elif "Embedding" in cat:
                    base_ms = 15.0
                else:
                    base_ms = self._default_service_time_ms

        # 2. Scale by input payload length
        payload = str(request.input_payload or request.prompt_or_payload or "")
        token_count = max(1, len(payload) // 4)
        
        # Generative scaling: autoregressive decode latency + prompt prefill latency
        meta = worker.adapter.metadata
        if meta and "Generative" in meta.model_type:
            target_new_tokens = request.max_tokens or 40
            decode_throughput = meta.throughput if meta and meta.throughput > 0 else 15.0
            # Prefill throughput is ~6x faster than token-by-token autoregressive generation
            prefill_throughput = max(30.0, decode_throughput * 6.0)
            decode_time_ms = (target_new_tokens / decode_throughput) * 1000.0
            prefill_time_ms = (token_count / prefill_throughput) * 1000.0
            return decode_time_ms + prefill_time_ms

        # Linear scaling for large inputs
        scale = 1.0 + max(0.0, (token_count - 100) / 500.0)
        return base_ms * scale

    def estimate_completion_time(self, worker: InferenceWorker, request: InferenceRequest) -> float:
        """ECT(w, r) = (A_w + Q_w) * ServiceTime + ExecTime(r)."""
        service_time_ms = self._estimate_service_time(worker, request)
        backlog = worker.active_requests + worker.queued_requests
        queue_wait_ms = backlog * service_time_ms
        return queue_wait_ms + service_time_ms

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None

        best_worker = candidates[0]
        min_ect = self.estimate_completion_time(best_worker, request)

        for w in candidates[1:]:
            ect = self.estimate_completion_time(w, request)
            if ect < min_ect:
                min_ect = ect
                best_worker = w

        return best_worker
