"""
adaptive_resilient.py: Fault-tolerant, self-healing resilient traffic scheduler.

Why this file exists:
Protects the inference pipeline against degraded or failing workers by:
- Circuit breaking and temporary cooldown on repeated failures
- Degradation avoidance and healthy worker prioritization
- Automatic health probing and recovery
- Controlled retry of eligible failed requests on alternative workers
- Idempotency guards to prevent duplicate execution of non-idempotent operations
"""

import logging
import threading
import time
from typing import Dict, List, Optional

from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    WorkerState,
)
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.worker_pool import InferenceWorker

logger = logging.getLogger(__name__)


class AdaptiveResilientScheduler(BaseScheduler):
    """Fault-tolerant scheduler with circuit breaking, degradation avoidance, and request retries."""

    def __init__(
        self,
        inner_scheduler: Optional[BaseScheduler] = None,
        max_consecutive_failures: int = 3,
        cooldown_sec: float = 5.0,
        max_retries: int = 2,
    ):
        self._inner = inner_scheduler or CapacityAwareScheduler()
        self._max_failures = max_consecutive_failures
        self._cooldown_sec = cooldown_sec
        self._max_retries = max_retries

        self._lock = threading.RLock()
        self._failures: Dict[str, int] = {}
        self._cooldown_expiry: Dict[str, float] = {}

    @property
    def name(self) -> str:
        return f"RESILIENT_{self._inner.name}"

    def record_success(self, worker_id: str) -> None:
        """Reset consecutive failure counter on successful execution."""
        with self._lock:
            self._failures[worker_id] = 0
            self._cooldown_expiry.pop(worker_id, None)

    def record_failure(self, worker_id: str) -> None:
        """Increment failure counter and trigger cooldown if threshold is breached."""
        with self._lock:
            count = self._failures.get(worker_id, 0) + 1
            self._failures[worker_id] = count
            if count >= self._max_failures:
                self._cooldown_expiry[worker_id] = time.time() + self._cooldown_sec
                logger.warning(
                    f"ResilientScheduler: Worker '{worker_id}' exceeded {self._max_failures} consecutive failures. "
                    f"Cooling down for {self._cooldown_sec}s."
                )

    def is_cooling_down(self, worker_id: str) -> bool:
        """Check if worker is currently in cooldown quarantine."""
        with self._lock:
            expiry = self._cooldown_expiry.get(worker_id, 0.0)
            if time.time() < expiry:
                return True
            if worker_id in self._cooldown_expiry:
                # Cooldown expired: allow worker back for probing
                del self._cooldown_expiry[worker_id]
                self._failures[worker_id] = 0
            return False

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None

        # Exclude workers that are failed, stopped, or in active cooldown
        active_candidates: List[InferenceWorker] = []
        for w in candidates:
            if not w.is_available():
                continue
            if self.is_cooling_down(w.worker_id):
                continue
            active_candidates.append(w)

        if not active_candidates:
            return None

        # Prioritize non-degraded workers first
        healthy_candidates = [
            w for w in active_candidates
            if w.state != WorkerState.DEGRADED and self._failures.get(w.worker_id, 0) == 0
        ]
        pool_to_schedule = healthy_candidates if healthy_candidates else active_candidates

        # Delegate ranking and capacity checks to inner scheduler
        return self._inner.select_worker(request, pool_to_schedule)

    def execute_with_resilience(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> InferenceResponse:
        """Execute request with automatic retry on alternative workers if failure occurs."""
        is_idempotent = request.metadata.get("idempotent", True)
        attempt_limit = (self._max_retries + 1) if is_idempotent else 1
        tried_worker_ids = set()
        last_response: Optional[InferenceResponse] = None

        start_time = time.perf_counter()

        for attempt in range(attempt_limit):
            # Filter out workers that already failed this specific request
            available_pool = [w for w in candidates if w.worker_id not in tried_worker_ids]
            selected = self.select_worker(request, available_pool)

            if selected is None:
                if last_response:
                    return last_response
                return InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=candidates[0].model_id if candidates else "unknown",
                    execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                    status="REJECTED",
                    error="ResilientScheduler: No healthy candidate worker available to serve request.",
                    metadata={"attempts": attempt},
                )

            tried_worker_ids.add(selected.worker_id)

            try:
                future = selected.submit(request)
                timeout_sec = request.timeout if request.timeout > 0 else 30.0
                response = future.result(timeout=timeout_sec + 1.0)

                if response.status == "SUCCESS":
                    self.record_success(selected.worker_id)
                    response.metadata["retry_attempts"] = attempt
                    return response
                else:
                    self.record_failure(selected.worker_id)
                    selected.trigger_cooldown(self._cooldown_sec)
                    response.metadata["attempt"] = attempt
                    last_response = response
                    logger.warning(
                        f"ResilientScheduler: Request {request.request_id} failed on {selected.worker_id}: {response.error}. "
                        f"Attempt {attempt + 1}/{attempt_limit}."
                    )

            except Exception as err:
                self.record_failure(selected.worker_id)
                selected.trigger_cooldown(self._cooldown_sec)
                last_response = InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=selected.model_id,
                    execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                    status="FAILED",
                    error=str(err),
                    metadata={"worker_id": selected.worker_id, "attempt": attempt},
                )
                logger.warning(
                    f"ResilientScheduler: Exception on {selected.worker_id}: {err}. Attempt {attempt + 1}/{attempt_limit}."
                )

            # Check if total request timeout was breached
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            max_ms = request.timeout_ms or (request.timeout * 1000.0)
            if elapsed_ms >= max_ms:
                return InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=candidates[0].model_id if candidates else "unknown",
                    execution_time_ms=round(elapsed_ms, 2),
                    status="TIMEOUT",
                    error=f"Resilient execution exceeded overall request timeout ({elapsed_ms:.1f}ms >= {max_ms:.1f}ms).",
                    metadata={"attempts": attempt + 1},
                )

        return last_response or InferenceResponse(
            request_id=request.request_id,
            result=None,
            model_id=candidates[0].model_id if candidates else "unknown",
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            status="FAILED",
            error=f"Exhausted all {attempt_limit} retry attempts across compatible workers.",
        )
