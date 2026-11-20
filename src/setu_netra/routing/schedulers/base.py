"""
base.py: Base abstract scheduler interface and decision abstractions.

Why this file exists:
Defines the common protocol for all traffic schedulers in SETU-NETRA, ensuring that
Round-Robin, Random, Least-Outstanding, SECT, Capacity-Aware, and Resilient schedulers
share an identical interface and can be benchmarked fairly without coupling.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from setu_netra.routing.contracts import InferenceRequest, SchedulingDecision
from setu_netra.routing.worker_pool import InferenceWorker


class BaseScheduler(ABC):
    """Abstract interface implemented by all worker schedulers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scheduling algorithm."""
        pass

    @abstractmethod
    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        """Select the optimal candidate worker for the given request.

        Args:
            request: Incoming inference request.
            candidates: List of candidate InferenceWorker instances capable of serving the model.

        Returns:
            Selected InferenceWorker instance, or None if no suitable worker is available.
        """
        pass

    def schedule(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> SchedulingDecision:
        """Produce an authoritative SchedulingDecision envelope."""
        available_candidates = [w for w in candidates if w.is_available()]
        if not available_candidates:
            return SchedulingDecision(
                selected_worker_id=None,
                model_id=candidates[0].model_id if candidates else "unknown",
                estimated_latency_ms=0.0,
                queue_wait_ms=0.0,
                strategy=self.name,
                reason="No candidate workers are currently available or healthy.",
                status="REJECTED",
            )

        selected = self.select_worker(request, available_candidates)
        if selected is None:
            return SchedulingDecision(
                selected_worker_id=None,
                model_id=available_candidates[0].model_id,
                estimated_latency_ms=0.0,
                queue_wait_ms=0.0,
                strategy=self.name,
                reason="Scheduler could not select an eligible worker.",
                status="REJECTED",
            )

        # Estimate queue wait and latency
        ewma = selected.ewma_latency_ms or 50.0
        queue_wait = (selected.queued_requests + selected.active_requests) * ewma

        return SchedulingDecision(
            selected_worker_id=selected.worker_id,
            model_id=selected.model_id,
            estimated_latency_ms=round(ewma, 2),
            queue_wait_ms=round(queue_wait, 2),
            strategy=self.name,
            reason=f"Scheduled via {self.name} algorithm.",
            status="SCHEDULED",
            metadata={
                "active_requests": selected.active_requests,
                "queued_requests": selected.queued_requests,
            },
        )
