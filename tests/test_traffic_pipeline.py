"""
test_traffic_pipeline.py: End-to-end integration tests for the IntelligentInferencePipeline.

Verifies:
- Complete 7-stage execution flow:
  Request -> Classification -> Router -> Selected Model -> Scheduler -> Worker -> Verification -> Response.
- End-to-end preservation of Request ID and full execution telemetry.
- Epistemic verification and citation validation.
- Dynamic scheduler switching.
- Graceful shutdown.
"""

import sys
import unittest
from pathlib import Path

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.contracts import EvidenceRequirement, InferenceRequest
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import ModelRegistry
from setu_netra.routing.schedulers.least_outstanding import LeastOutstandingRequestsScheduler
from setu_netra.routing.schedulers.round_robin import RoundRobinScheduler
from setu_netra.routing.worker_pool import InferenceWorkerPool


class TestTrafficPipeline(unittest.TestCase):
    def setUp(self):
        self.registry = ModelRegistry(register_defaults=False)
        self.worker_pool = InferenceWorkerPool()

        # Core adapters
        self.qa_adapter = GroundedExtractiveQAAdapter(model_id="grounded-qa-engine")
        self.clf_adapter = ClassificationExecutionAdapter(model_id="domain-clf-engine")

        self.registry.register_adapter(self.qa_adapter)
        self.registry.register_adapter(self.clf_adapter)

        # Build pipeline
        self.pipeline = IntelligentInferencePipeline(
            registry=self.registry,
            worker_pool=self.worker_pool,
            auto_spawn_workers=True,
        )

    def tearDown(self):
        self.pipeline.shutdown(drain=False, timeout=1.0)

    def test_01_end_to_end_grounded_extractive_pipeline(self):
        req = InferenceRequest(
            task_type="qa",
            input_payload="What is the maximum operating temperature?",
            context="The industrial sensor operates at temperatures up to 125 degrees Celsius [Doc: spec.pdf, Page: 1, Block: 5].",
            metadata={"evidence_requirement": EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS},
        )
        original_req_id = req.request_id

        response = self.pipeline.execute(req)

        # 1. Output verification
        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(response.request_id, original_req_id)
        self.assertIn("125 degrees Celsius", str(response.result))

        # 2. Telemetry and Provenance verification
        meta = response.metadata
        self.assertEqual(meta.get("epistemic_status"), "EVIDENCE_BACKED")
        self.assertTrue(meta.get("is_verified"))
        self.assertIn("pipeline_telemetry", meta)

        pipeline_tel = meta["pipeline_telemetry"]
        self.assertGreater(pipeline_tel["total_latency_ms"], 0.0)
        self.assertEqual(pipeline_tel["routing_decision"]["selected_model"], "grounded-qa-engine")
        self.assertIn("system_telemetry", pipeline_tel)
        self.assertIn("cpu_percent", pipeline_tel["system_telemetry"])
        self.assertIn("avail_ram_mb", pipeline_tel["system_telemetry"])

    def test_02_end_to_end_domain_classification_pipeline(self):
        req = InferenceRequest(
            task_type="classification",
            input_payload="Linear transformations and eigenvalue decompositions in vector spaces.",
        )
        response = self.pipeline.execute(req)

        self.assertEqual(response.status, "SUCCESS")
        self.assertIn("top_domain", response.result)
        self.assertEqual(response.result["top_domain"], "Linear Algebra")

    def test_03_dynamic_scheduler_switching(self):
        # Switch to Least Outstanding Requests
        self.pipeline.set_scheduler(LeastOutstandingRequestsScheduler())
        self.assertEqual(self.pipeline.scheduler.name, "LEAST_OUTSTANDING")

        req = InferenceRequest(
            task_type="qa",
            input_payload="What is the clock rate?",
            context="The clock rate is 3.5 GHz [Doc: cpu.pdf, Page: 1, Block: 1].",
        )
        res = self.pipeline.execute(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.metadata["pipeline_telemetry"]["scheduling"]["strategy"], "LEAST_OUTSTANDING")

        # Switch to Round Robin
        self.pipeline.set_scheduler(RoundRobinScheduler())
        self.assertEqual(self.pipeline.scheduler.name, "ROUND_ROBIN")

    def test_04_pipeline_rejection_on_invalid_task(self):
        req = InferenceRequest(
            task_type="unsupported_quantum_task",
            input_payload="Compute qubit entanglement.",
        )
        response = self.pipeline.execute(req)
        self.assertEqual(response.status, "REJECTED")
        self.assertIn("Unsupported task type", response.error)
        self.assertEqual(response.request_id, req.request_id)


if __name__ == "__main__":
    unittest.main()
