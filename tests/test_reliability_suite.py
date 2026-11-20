"""
test_reliability_suite.py: Automated reliability and fault recovery tests for Stage 6.

Tests:
1. Worker crash failover across alternate workers.
2. Worker execution and queue timeout enforcement.
3. Queue saturation and backpressure signal handling.
4. Circuit breaker activation on consecutive crashes and subsequent recovery.
5. Idempotency guard: non-idempotent tasks are strictly executed at most once.
6. Request correlation ID preservation across retries.
"""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.reliability_runner import ReliabilityBenchmarkRunner


class TestReliabilitySuite(unittest.TestCase):
    def setUp(self):
        self.runner = ReliabilityBenchmarkRunner()

    def test_01_worker_crash_failover(self):
        res = self.runner.test_01_worker_crash_and_failover()
        self.assertTrue(res["passed"], f"Failover failed: {res}")
        self.assertEqual(res["servicing_worker"], "w_backup")
        self.assertTrue(res["correlation_id_preserved"])

    def test_02_execution_timeout(self):
        res = self.runner.test_02_execution_and_queue_timeouts()
        self.assertTrue(res["passed"], f"Timeout enforcement failed: {res}")
        self.assertEqual(res["status"], "TIMEOUT")

    def test_03_queue_saturation(self):
        res = self.runner.test_03_queue_saturation_backpressure()
        self.assertTrue(res["passed"], f"Queue saturation backpressure failed: {res}")

    def test_04_circuit_breaker(self):
        res = self.runner.test_04_circuit_breaker_tripping_and_recovery()
        self.assertTrue(res["passed"], f"Circuit breaker test failed: {res}")
        self.assertTrue(res["circuit_breaker_tripped"])
        self.assertTrue(res["circuit_breaker_recovered"])

    def test_05_idempotency_guard(self):
        res = self.runner.test_05_non_idempotent_task_retry_prevention()
        self.assertTrue(res["passed"], f"Idempotency guard failed: {res}")
        self.assertEqual(res["attempts_performed"], 1)

    def test_06_stale_telemetry(self):
        res = self.runner.test_06_stale_telemetry_detection()
        self.assertTrue(res["passed"], f"Stale telemetry test failed: {res}")


if __name__ == "__main__":
    unittest.main()
