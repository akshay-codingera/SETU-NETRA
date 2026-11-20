"""
test_adaptive_router.py: Test suite for AdaptiveModelRouter.

Verifies:
- Task-type deterministic routing (OCR, embedding, classification, extractive QA, generative QA).
- Cognitive intent routing (COMPARISON -> generative, FACTUAL -> extractive).
- SLA / latency constraint enforcement (tight latency budget prevents slow SLMs).
- Unsupported task rejection.
- Model unavailability and fallback behavior.
"""

import sys
import unittest
from pathlib import Path

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.embedding_adapter import EmbeddingExecutionAdapter
from setu_netra.routing.adapters.generative_adapter import LocalGenerativeAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.adapters.ocr_adapter import OCRExecutionAdapter
from setu_netra.routing.contracts import (
    EvidenceRequirement,
    InferenceRequest,
    ModelAvailability,
    ModelHealth,
    QualityRequirement,
)
from setu_netra.routing.registry import ModelRegistry
from setu_netra.routing.router import AdaptiveModelRouter


class TestAdaptiveModelRouter(unittest.TestCase):
    def setUp(self):
        # Clean isolated registry with core adapters
        self.registry = ModelRegistry(register_defaults=False)
        self.extractive_adapter = GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1")
        self.generative_adapter = LocalGenerativeAdapter(model_id="smollm2-135m-instruct")
        self.embed_adapter = EmbeddingExecutionAdapter(model_id="all-minilm-l6-v2")
        self.ocr_adapter = OCRExecutionAdapter(model_id="easyocr-craft-crnn")
        self.clf_adapter = ClassificationExecutionAdapter(model_id="academic-domain-classifier-v1")

        self.registry.register_adapter(self.extractive_adapter)
        self.registry.register_adapter(self.generative_adapter)
        self.registry.register_adapter(self.embed_adapter)
        self.registry.register_adapter(self.ocr_adapter)
        self.registry.register_adapter(self.clf_adapter)

        self.router = AdaptiveModelRouter(self.registry)

    def test_01_route_ocr_task(self):
        req = InferenceRequest(task_type="ocr", input_payload="document_page_1.png")
        decision = self.router.route(req)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.selected_model_id, "easyocr-craft-crnn")
        self.assertEqual(decision.task_type, "ocr")

    def test_02_route_embedding_task(self):
        req = InferenceRequest(task_type="embedding", input_payload=["Vectorize this text"])
        decision = self.router.route(req)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.selected_model_id, "all-minilm-l6-v2")

    def test_03_route_domain_classification(self):
        req = InferenceRequest(
            task_type="domain_detection",
            input_payload="Eigenvalue decomposition in linear vector spaces",
        )
        decision = self.router.route(req)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.selected_model_id, "academic-domain-classifier-v1")

    def test_04_route_strict_evidence_extractive_qa(self):
        req = InferenceRequest(
            task_type="extractive_qa",
            input_payload="What is the operating frequency?",
            context="The device operates at 144 Hz.",
            metadata={"evidence_requirement": EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS},
        )
        decision = self.router.route(req)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.selected_model_id, "grounded-extractive-qa-v1")
        self.assertIn("Extractive QA", decision.reason)

    def test_05_route_comparative_generative_qa(self):
        req = InferenceRequest(
            task_type="qa",
            input_payload="Compare the performance characteristics of B-trees versus Hash indexes.",
            metadata={"intent": "COMPARISON"},
            timeout_ms=5000,
        )
        decision = self.router.route(req)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.selected_model_id, "smollm2-135m-instruct")

    def test_06_route_tight_latency_budget_fallback(self):
        # A generative request with an impossibly tight latency SLA of 500ms
        req = InferenceRequest(
            task_type="generative_qa",
            input_payload="Explain backpropagation in deep neural networks.",
            timeout_ms=500,
        )
        decision = self.router.route(req)
        # Should fall back to fast extractive engine or reject because 500ms < 1500ms
        self.assertEqual(decision.status, "FALLBACK")
        self.assertEqual(decision.selected_model_id, "grounded-extractive-qa-v1")
        self.assertIn("Strict SLA", decision.reason)

    def test_07_route_unsupported_task_rejection(self):
        req = InferenceRequest(task_type="quantum_teleportation", input_payload="Teleport state.")
        decision = self.router.route(req)
        self.assertEqual(decision.status, "REJECTED")
        self.assertIsNone(decision.selected_model_id)
        self.assertIn("Unsupported task type", decision.reason)

    def test_08_route_unavailable_model_fallback(self):
        # Mark extractive model as UNAVAILABLE
        self.registry.set_model_availability("grounded-extractive-qa-v1", ModelAvailability.UNAVAILABLE)

        req = InferenceRequest(
            task_type="qa",
            input_payload="What is the clock speed?",
        )
        decision = self.router.route(req)
        # Should route to available generative fallback
        self.assertIn(decision.status, ("ROUTED", "FALLBACK"))
        self.assertEqual(decision.selected_model_id, "smollm2-135m-instruct")


if __name__ == "__main__":
    unittest.main()
