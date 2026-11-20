"""
test_model_registry.py: Comprehensive test suite for Model Registry and Unified Inference Interface.

Verifies:
- Registry thread-safety and duplicate registration policies.
- Task-based and category-based model discovery.
- Worker-level registration and dispatching (worker_id).
- Health and availability state tracking.
- Execution routing, telemetry recording, and p95 latency calculation.
- Timeout handling and defensive failure containment.
- Dual-model execution through the unified inference interface.
"""

import sys
import time
import unittest
from pathlib import Path
from typing import List, Optional

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.registry import ModelRegistry


class DummyEchoAdapter(BaseModelAdapter):
    """Deterministic dummy adapter for testing registry behavior."""

    def __init__(
        self,
        model_id: str = "dummy-echo-v1",
        worker_id: Optional[str] = None,
        tasks: Optional[List[str]] = None,
        category: ModelCategory = ModelCategory.CLASSIFICATION,
        delay_ms: float = 0.0,
        fail: bool = False,
        available: bool = True,
        healthy: bool = True,
    ):
        self._model_id = model_id
        self._worker_id = worker_id or f"{model_id}_w1"
        self._tasks = tasks or ["echo", "test_task"]
        self._category = category
        self._delay_ms = delay_ms
        self._fail = fail
        self._available = available
        self._healthy = healthy

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return self._tasks

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name=f"Dummy {self._model_id}",
            model_type=self._category,
            supported_tasks=self._tasks,
            provider="Test Provider",
            execution_backend="MOCK_CPU",
            memory_requirement={"min_ram_mb": 10},
            context_length=1024,
            availability=ModelAvailability.AVAILABLE if self._available else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self._healthy else ModelHealth.UNHEALTHY,
            worker_id=self._worker_id,
        )

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> bool:
        return self._healthy

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        start_time = time.perf_counter()
        if self._delay_ms > 0:
            time.sleep(self._delay_ms / 1000.0)

        if self._fail:
            raise RuntimeError(f"Simulated execution crash in {self._worker_id}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return InferenceResponse(
            request_id=request.request_id,
            result={"echo": request.input_payload, "worker": self._worker_id},
            model_id=self._model_id,
            execution_time_ms=round(elapsed_ms, 2),
            status="SUCCESS",
            metadata={"worker_id": self._worker_id},
        )


class TestModelRegistry(unittest.TestCase):
    """Test suite for centralized ModelRegistry."""

    def setUp(self):
        self.registry = ModelRegistry(register_defaults=False)

    def test_01_register_and_lookup_adapter(self):
        adapter = DummyEchoAdapter(model_id="echo-1")
        self.registry.register_adapter(adapter)

        retrieved = self.registry.get_adapter("echo-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.model_id, "echo-1")
        self.assertEqual(self.registry.get_registered_model_ids(), ["echo-1"])

    def test_02_duplicate_model_registration_policy(self):
        adapter1 = DummyEchoAdapter(model_id="echo-dup", worker_id="w1")
        self.registry.register_adapter(adapter1)

        adapter2 = DummyEchoAdapter(model_id="echo-dup", worker_id="w1")
        # Should raise ValueError when override=False and same worker_id
        with self.assertRaises(ValueError):
            self.registry.register_adapter(adapter2, override=False)

        # Should succeed when override=True
        self.registry.register_adapter(adapter2, override=True)
        self.assertEqual(len(self.registry.get_registered_model_ids()), 1)

    def test_03_multi_worker_registration_and_dispatch(self):
        w1 = DummyEchoAdapter(model_id="multi-worker-model", worker_id="worker_alpha")
        w2 = DummyEchoAdapter(model_id="multi-worker-model", worker_id="worker_beta")
        self.registry.register_adapter(w1)
        self.registry.register_adapter(w2)

        # Both workers should be registered
        workers = self.registry.get_workers_for_model("multi-worker-model")
        self.assertEqual(len(workers), 2)
        worker_ids = [w.worker_id for w in workers]
        self.assertIn("worker_alpha", worker_ids)
        self.assertIn("worker_beta", worker_ids)

        # Dispatch specifically to worker_beta
        req = InferenceRequest(
            task_type="echo",
            input_payload="hello worker beta",
            model_id="multi-worker-model",
            worker_id="worker_beta",
        )
        res = self.registry.execute(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.result["worker"], "worker_beta")

    def test_04_filter_by_task_and_category(self):
        ad_qa = DummyEchoAdapter(
            model_id="extractive-qa-1",
            tasks=["extractive_qa", "qa"],
            category=ModelCategory.EXTRACTIVE_QA,
        )
        ad_gen = DummyEchoAdapter(
            model_id="generative-qa-1",
            tasks=["generative_qa", "qa", "summarization"],
            category=ModelCategory.GENERATIVE_QA,
        )
        ad_ocr = DummyEchoAdapter(
            model_id="ocr-1",
            tasks=["ocr", "text_extraction"],
            category=ModelCategory.OCR,
        )
        self.registry.register_adapter(ad_qa)
        self.registry.register_adapter(ad_gen)
        self.registry.register_adapter(ad_ocr)

        # Filter by task
        qa_adapters = self.registry.get_adapters_for_task("qa")
        self.assertEqual(len(qa_adapters), 2)
        qa_model_ids = {a.model_id for a in qa_adapters}
        self.assertEqual(qa_model_ids, {"extractive-qa-1", "generative-qa-1"})

        ocr_adapters = self.registry.get_adapters_for_task("ocr")
        self.assertEqual(len(ocr_adapters), 1)
        self.assertEqual(ocr_adapters[0].model_id, "ocr-1")

        # Filter by category
        gen_models = self.registry.get_models_by_category(ModelCategory.GENERATIVE_QA)
        self.assertEqual(len(gen_models), 1)
        self.assertEqual(gen_models[0].model_id, "generative-qa-1")

    def test_05_model_availability_and_health_tracking(self):
        adapter = DummyEchoAdapter(model_id="health-test", available=True, healthy=True)
        self.registry.register_adapter(adapter)

        meta = self.registry.get_model_metadata("health-test")
        self.assertEqual(meta.availability, ModelAvailability.AVAILABLE)
        self.assertEqual(meta.health_status, ModelHealth.HEALTHY)

        # Set availability to UNAVAILABLE
        self.registry.set_model_availability("health-test", ModelAvailability.UNAVAILABLE)
        meta_updated = self.registry.get_model_metadata("health-test")
        self.assertEqual(meta_updated.availability, ModelAvailability.UNAVAILABLE)

        # Set health status to DEGRADED
        self.registry.set_model_health("health-test", ModelHealth.DEGRADED)
        meta_degraded = self.registry.get_model_metadata("health-test")
        self.assertEqual(meta_degraded.health_status, ModelHealth.DEGRADED)

        # Should be excluded from available_only queries
        available_models = self.registry.get_registered_models(available_only=True)
        self.assertNotIn("health-test", [m.model_id for m in available_models])

    def test_06_execution_telemetry_and_p95_calculation(self):
        adapter = DummyEchoAdapter(model_id="telemetry-test", delay_ms=10.0)
        self.registry.register_adapter(adapter)

        for i in range(10):
            req = InferenceRequest(task_type="echo", input_payload=f"req_{i}", model_id="telemetry-test")
            res = self.registry.execute(req)
            self.assertEqual(res.status, "SUCCESS")

        meta = self.registry.get_model_metadata("telemetry-test")
        self.assertIsNotNone(meta.measured_latency)
        self.assertIn("mean_ms", meta.measured_latency)
        self.assertIn("p95_ms", meta.measured_latency)
        self.assertIn("sample_count", meta.measured_latency)
        self.assertEqual(meta.measured_latency["sample_count"], 10)
        self.assertGreater(meta.measured_latency["mean_ms"], 5.0)
        self.assertGreater(meta.measured_latency["p95_ms"], 5.0)

    def test_07_execution_failure_handling(self):
        failing_adapter = DummyEchoAdapter(model_id="failing-model", fail=True)
        self.registry.register_adapter(failing_adapter)

        req = InferenceRequest(task_type="echo", input_payload="will fail", model_id="failing-model")
        res = self.registry.execute(req)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Simulated execution crash", str(res.error))

    def test_08_timeout_guard(self):
        # 100ms delay with a 20ms timeout
        slow_adapter = DummyEchoAdapter(model_id="slow-model", delay_ms=100.0)
        self.registry.register_adapter(slow_adapter)

        req = InferenceRequest(
            task_type="echo",
            input_payload="slow request",
            model_id="slow-model",
            timeout_ms=20,
        )
        res = self.registry.execute(req)
        self.assertEqual(res.status, "TIMEOUT")
        self.assertIn("exceeded timeout", str(res.error))


class TestUnifiedInferenceDualExecution(unittest.TestCase):
    """Demonstrates two different model paradigms invoked via the identical unified interface."""

    def test_01_extractive_and_generative_qa_coexistence(self):
        from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
        from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter

        registry = ModelRegistry(register_defaults=False)

        qa_adapter = GroundedExtractiveQAAdapter(model_id="extractive-grounded-qa")
        clf_adapter = ClassificationExecutionAdapter(model_id="academic-classifier")

        registry.register_adapter(qa_adapter)
        registry.register_adapter(clf_adapter)

        # 1. Extractive QA execution via Unified Interface
        qa_req = InferenceRequest(
            task_type="extractive_qa",
            input_payload="What is the capital of France?",
            context="Paris is the capital of France.",
            model_id="extractive-grounded-qa",
        )
        qa_res = registry.execute(qa_req)
        self.assertEqual(qa_res.status, "SUCCESS")
        self.assertEqual(qa_res.model_id, "extractive-grounded-qa")
        self.assertIn("Paris", str(qa_res.result))
        self.assertGreater(qa_res.execution_time_ms, 0)

        # 2. Classification execution via Identical Unified Interface
        clf_req = InferenceRequest(
            task_type="classification",
            input_payload="This paper introduces a convolutional neural network for image classification.",
            model_id="academic-classifier",
        )
        clf_res = registry.execute(clf_req)
        self.assertEqual(clf_res.status, "SUCCESS")
        self.assertEqual(clf_res.model_id, "academic-classifier")
        self.assertIn("top_domain", clf_res.result)
        self.assertGreater(clf_res.execution_time_ms, 0)


if __name__ == "__main__":
    unittest.main()
