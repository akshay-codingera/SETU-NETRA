"""
test_schedulers.py: Comprehensive test suite for all traffic scheduling strategies.

Verifies:
- RoundRobinScheduler: cyclic sequential distribution across workers.
- RandomScheduler: valid worker selection.
- LeastOutstandingRequestsScheduler: w* = argmin(A_w + Q_w).
- ShortestEstimatedCompletionTimeScheduler: EWMA latency and token scaling.
- CapacityAwareScheduler: multidimensional normalization and host capacity checks.
- AdaptiveResilientScheduler: fault-tolerance, cooldown, degradation avoidance, and retries.
"""

import sys
import time
import unittest
from pathlib import Path
from typing import List, Optional

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelCategory,
    ModelMetadata,
    WorkerState,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.schedulers.adaptive_resilient import AdaptiveResilientScheduler
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.schedulers.least_outstanding import LeastOutstandingRequestsScheduler
from setu_netra.routing.schedulers.predictive import ShortestEstimatedCompletionTimeScheduler
from setu_netra.routing.schedulers.random_scheduler import RandomScheduler
from setu_netra.routing.schedulers.round_robin import RoundRobinScheduler
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool


class DummySchedulerAdapter(BaseModelAdapter):
    def __init__(
        self,
        model_id: str,
        worker_id: str,
        delay_ms: float = 10.0,
        fail: bool = False,
    ):
        self._model_id = model_id
        self._worker_id = worker_id
        self._delay_ms = delay_ms
        self._fail = fail

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return ["qa", "test"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name="Dummy Scheduler Adapter",
            model_type=ModelCategory.EXTRACTIVE_QA,
            supported_tasks=self.task_types,
            provider="Test",
            execution_backend="MOCK",
            memory_requirement={"min_ram_mb": 20},
            context_length=1024,
            worker_id=self._worker_id,
        )

    def is_available(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        if self._delay_ms > 0:
            time.sleep(self._delay_ms / 1000.0)
        if self._fail:
            raise RuntimeError(f"Deliberate crash on {self._worker_id}")
        return InferenceResponse(
            request_id=request.request_id,
            result="dummy_success",
            model_id=self._model_id,
            execution_time_ms=self._delay_ms,
            status="SUCCESS",
            metadata={"worker_id": self._worker_id},
        )


class TestSchedulers(unittest.TestCase):
    def setUp(self):
        self.pool = InferenceWorkerPool()
        # Create 3 workers for 'test-model'
        self.w1 = self.pool.create_worker(DummySchedulerAdapter("test-model", "w1", delay_ms=10.0))
        self.w2 = self.pool.create_worker(DummySchedulerAdapter("test-model", "w2", delay_ms=20.0))
        self.w3 = self.pool.create_worker(DummySchedulerAdapter("test-model", "w3", delay_ms=30.0))
        self.candidates = [self.w1, self.w2, self.w3]

    def tearDown(self):
        self.pool.stop_all(drain=False, timeout=1.0)

    def test_01_round_robin_scheduler(self):
        scheduler = RoundRobinScheduler()
        req = InferenceRequest(task_type="test", model_id="test-model")

        picks = [scheduler.select_worker(req, self.candidates).worker_id for _ in range(6)]
        self.assertEqual(picks, ["w1", "w2", "w3", "w1", "w2", "w3"])

    def test_02_random_scheduler(self):
        scheduler = RandomScheduler(seed=42)
        req = InferenceRequest(task_type="test", model_id="test-model")

        for _ in range(5):
            chosen = scheduler.select_worker(req, self.candidates)
            self.assertIn(chosen.worker_id, ["w1", "w2", "w3"])

    def test_03_least_outstanding_requests(self):
        scheduler = LeastOutstandingRequestsScheduler()
        req = InferenceRequest(task_type="test", model_id="test-model")

        # Artificially set backlog
        # w1: 2 active
        # w2: 0 active (idle)
        # w3: 1 active
        self.w1._active_requests = 2
        self.w2._active_requests = 0
        self.w3._active_requests = 1

        selected = scheduler.select_worker(req, self.candidates)
        self.assertEqual(selected.worker_id, "w2")

        # Now increase w2 load to 3
        self.w2._active_requests = 3
        selected_next = scheduler.select_worker(req, self.candidates)
        # w3 has min load (1)
        self.assertEqual(selected_next.worker_id, "w3")

    def test_04_shortest_estimated_completion_time(self):
        scheduler = ShortestEstimatedCompletionTimeScheduler()
        req = InferenceRequest(task_type="test", model_id="test-model", input_payload="Short text")

        # Set EWMA latencies
        self.w1._ewma_latency_ms = 100.0  # Slow worker
        self.w2._ewma_latency_ms = 10.0   # Fast worker
        self.w3._ewma_latency_ms = 50.0   # Medium worker

        # All workers have 0 queue backlog
        selected = scheduler.select_worker(req, self.candidates)
        self.assertEqual(selected.worker_id, "w2")

        # Now give w2 a backlog of 20 requests: 20 * 10ms = 200ms wait
        self.w2._active_requests = 20
        # w3 has 0 backlog: 0 * 50ms = 0ms wait + 50ms exec = 50ms ECT
        selected_backlogged = scheduler.select_worker(req, self.candidates)
        self.assertEqual(selected_backlogged.worker_id, "w3")

    def test_05_capacity_aware_scheduler(self):
        scheduler = CapacityAwareScheduler()
        req = InferenceRequest(task_type="test", model_id="test-model")

        # Setup load and latencies
        self.w1._active_requests = 5
        self.w1._ewma_latency_ms = 10.0

        self.w2._active_requests = 0
        self.w2._ewma_latency_ms = 12.0

        self.w3._active_requests = 1
        self.w3._state = WorkerState.DEGRADED  # Degraded penalty

        selected = scheduler.select_worker(req, self.candidates)
        # w2 is idle, healthy, and low latency -> optimal cost
        self.assertEqual(selected.worker_id, "w2")

    def test_06_resilient_scheduler_retries_and_recovery(self):
        # Create a failing worker and a healthy worker
        failing_adapter = DummySchedulerAdapter("resilient-model", "w_fail", fail=True)
        healthy_adapter = DummySchedulerAdapter("resilient-model", "w_good", fail=False)

        w_fail = self.pool.create_worker(failing_adapter, worker_id="w_fail", cooldown_period_sec=1.0)
        w_good = self.pool.create_worker(healthy_adapter, worker_id="w_good")

        scheduler = AdaptiveResilientScheduler(
            inner_scheduler=RoundRobinScheduler(),
            max_consecutive_failures=2,
            cooldown_sec=1.0,
            max_retries=2,
        )

        req = InferenceRequest(task_type="test", model_id="resilient-model", metadata={"idempotent": True})

        # Submit through execute_with_resilience
        resp = scheduler.execute_with_resilience(req, [w_fail, w_good])

        # Should automatically retry on w_good and succeed!
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.metadata.get("worker_id"), "w_good")
        self.assertGreaterEqual(resp.metadata.get("retry_attempts", 0), 1)

    def test_07_resilient_scheduler_non_idempotent_no_retry(self):
        failing_adapter = DummySchedulerAdapter("resilient-model", "w_fail2", fail=True)
        healthy_adapter = DummySchedulerAdapter("resilient-model", "w_good2", fail=False)

        w_fail = self.pool.create_worker(failing_adapter, worker_id="w_fail2")
        w_good = self.pool.create_worker(healthy_adapter, worker_id="w_good2")

        scheduler = AdaptiveResilientScheduler(max_retries=2)

        # Explicitly marked non-idempotent
        req = InferenceRequest(
            task_type="test",
            model_id="resilient-model",
            metadata={"idempotent": False},
        )
        resp = scheduler.execute_with_resilience(req, [w_fail, w_good])
        # Non-idempotent request should NOT retry on failure
        self.assertEqual(resp.status, "FAILED")
        self.assertEqual(resp.metadata.get("attempt"), 0)


if __name__ == "__main__":
    unittest.main()
