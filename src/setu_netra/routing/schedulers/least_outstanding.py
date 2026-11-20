"""
least_outstanding.py: Least Outstanding Requests (LOR) traffic scheduler.

Why this file exists:
Dispatches requests to the worker with the lowest instantaneous load:
w* = argmin_{w} (A_w + Q_w)
where A_w is active requests and Q_w is queued requests.
"""

from typing import List, Optional

from setu_netra.routing.contracts import InferenceRequest
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.worker_pool import InferenceWorker


class LeastOutstandingRequestsScheduler(BaseScheduler):
    """Schedules requests to the worker with minimum outstanding (active + queued) backlog."""

    @property
    def name(self) -> str:
        return "LEAST_OUTSTANDING"

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None

        # w* = argmin(A_w + Q_w)
        best_worker = candidates[0]
        min_load = best_worker.active_requests + best_worker.queued_requests

        for w in candidates[1:]:
            load = w.active_requests + w.queued_requests
            if load < min_load:
                min_load = load
                best_worker = w
            elif load == min_load:
                # Tie-breaking: prioritize lower historical latency if available
                w_lat = w.ewma_latency_ms if w.ewma_latency_ms is not None else 9999.0
                best_lat = best_worker.ewma_latency_ms if best_worker.ewma_latency_ms is not None else 9999.0
                if w_lat < best_lat:
                    best_worker = w

        return best_worker
