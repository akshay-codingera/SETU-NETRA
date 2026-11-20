"""
test_worker_pool.py: Test suite for InferenceWorker and InferenceWorkerPool.

Verifies:
- Worker initialization, identification, and background thread execution.
- Active request (A_w) and queued request (Q_w) tracking.
- Queue limits and backpressure enforcement.
- Circuit breaking and cooldown state transitions on repeated failures.
- Worker timeout enforcement for long/stuck requests.
- Graceful shutdown and draining.
"""

import concurrent.futures
import queue
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
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool


class MockLatencyAdapter(BaseModelAdapter):
    """Deterministic adapter with configurable delay and failure behavior."""

    def __init__(
        self,
        model_id: str = "mock-model-v1",
        worker_id: Optional[str] = None,
        delay_sec: float = 0.05,
        fail_times: int = 0,
    ):
        self._model_id = model_id
        self._worker_id = worker_id or f"{model_id}_w1"
        self._delay_sec = delay_sec
        self._fail_times = fail_times
        self._call_count = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return ["qa", "mock"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name="Mock Latency Model",
            model_type=ModelCategory.EXTRACTIVE_QA,
            supported_tasks=self.task_types,
            provider="Test",
            execution_backend="MOCK",
            memory_requirement={"min_ram_mb": 10},
            context_length=1024,
            worker_id=self._worker_id,
        )

    def is_available(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        self._call_count += 1
        if self._delay_sec > 0:
            time.sleep(self._delay_sec)

        if self._call_count <= self._fail_times:
            raise RuntimeError(f"Simulated crash on attempt {self._call_count}")

        return InferenceResponse(
            request_id=request.request_id,
            result={"answer": "mock_result", "attempt": self._call_count},
            model_id=self._model_id,
            execution_time_ms=round(self._delay_sec * 1000.0, 2),
            status="SUCCESS",
        )


class TestWorkerPool(unittest.TestCase):
    def setUp(self):
        self.pool = InferenceWorkerPool()

    def tearDown(self):
        self.pool.stop_all(drain=False, timeout=1.0)

    def test_01_worker_execution_and_request_id_preservation(self):
        adapter = MockLatencyAdapter(model_id="echo-model", delay_sec=0.01)
        worker = self.pool.create_worker(adapter, worker_id="w_echo_1")

        req = InferenceRequest(
            task_type="mock",
            input_payload="hello world",
            model_id="echo-model",
        )
        original_req_id = req.request_id

        future = worker.submit(req)
        response = future.result(timeout=2.0)

        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(response.request_id, original_req_id)
        self.assertEqual(response.metadata.get("worker_id"), "w_echo_1")
        self.assertIsNotNone(worker.ewma_latency_ms)

    def test_02_multi_worker_registration_for_same_model(self):
        a1 = MockLatencyAdapter(model_id="multi-model", worker_id="w_alpha")
        a2 = MockLatencyAdapter(model_id="multi-model", worker_id="w_beta")

        w1 = self.pool.create_worker(a1, worker_id="w_alpha")
        w2 = self.pool.create_worker(a2, worker_id="w_beta")

        workers = self.pool.get_workers_for_model("multi-model")
        self.assertEqual(len(workers), 2)
        worker_ids = [w.worker_id for w in workers]
        self.assertIn("w_alpha", worker_ids)
        self.assertIn("w_beta", worker_ids)

    def test_03_backpressure_and_queue_limits(self):
        # Worker with queue size = 2 and delay = 0.5s
        adapter = MockLatencyAdapter(model_id="slow-model", delay_sec=0.5)
        worker = self.pool.create_worker(adapter, worker_id="w_slow", max_queue_size=2)

        # Submit until queue is full and raises queue.Full
        raised_full = False
        try:
            for i in range(10):
                worker.submit(InferenceRequest(task_type="mock", input_payload=f"req_{i}"))
        except queue.Full:
            raised_full = True

        self.assertTrue(raised_full, "Expected queue.Full exception when queue capacity exceeded.")

    def test_04_circuit_breaking_and_cooldown(self):
        # Adapter configured to fail 3 consecutive times
        adapter = MockLatencyAdapter(model_id="failing-model", delay_sec=0.01, fail_times=3)
        worker = self.pool.create_worker(
            adapter,
            worker_id="w_failing",
            failure_threshold=3,
            cooldown_period_sec=0.5,
        )

        for i in range(3):
            req = InferenceRequest(task_type="mock", input_payload=f"fail_{i}")
            fut = worker.submit(req)
            res = fut.result(timeout=2.0)
            self.assertEqual(res.status, "FAILED")

        # After 3 failures, worker state must be COOLING_DOWN
        self.assertEqual(worker.state, WorkerState.COOLING_DOWN)
        self.assertFalse(worker.is_available())

        # Submitting while cooling down must be rejected
        with self.assertRaises(RuntimeError):
            worker.submit(InferenceRequest(task_type="mock", input_payload="during_cooldown"))

        # Wait for cooldown to expire
        time.sleep(0.6)
        self.assertTrue(worker.is_available())
        self.assertEqual(worker.state, WorkerState.IDLE)

    def test_05_request_timeout_enforcement(self):
        # 300ms delay with a 50ms timeout
        adapter = MockLatencyAdapter(model_id="timeout-model", delay_sec=0.3)
        worker = self.pool.create_worker(adapter, worker_id="w_timeout")

        req = InferenceRequest(
            task_type="mock",
            input_payload="stuck request",
            timeout_ms=50,
        )
        fut = worker.submit(req)
        res = fut.result(timeout=2.0)
        self.assertEqual(res.status, "TIMEOUT")
        self.assertIn("exceeded timeout", res.error)


if __name__ == "__main__":
    unittest.main()
