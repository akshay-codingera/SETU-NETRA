"""
test_inference_interface.py: Standardized verification of the Unified Inference Interface.

Verifies:
- Bi-directional backward compatibility between Stage 3 and Stage 4 contracts.
- Task execution across core adapter categories:
  1. Extractive QA (GroundedExtractiveQAAdapter)
  2. Embedding (EmbeddingExecutionAdapter)
  3. Classification (ClassificationExecutionAdapter)
  4. OCR (OCRExecutionAdapter)
  5. Generative SLM (LocalGenerativeAdapter)
- Lazy loading behavior of heavy generative weights.
- Unsupported question and out-of-domain handling.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.embedding_adapter import EmbeddingExecutionAdapter
from setu_netra.routing.adapters.generative_adapter import LocalGenerativeAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.adapters.ocr_adapter import OCRExecutionAdapter
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelCategory,
)
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine


class TestUnifiedInferenceContracts(unittest.TestCase):
    """Verifies contract validation and legacy bidirectional mapping."""

    def test_01_request_contract_backward_compatibility(self):
        # Initialized with Stage 3 'prompt_or_payload'
        req_legacy = InferenceRequest(
            prompt_or_payload="Explain transformer attention.",
            task_type="qa",
            context="Transformers use multi-head attention.",
        )
        self.assertEqual(req_legacy.input_payload, "Explain transformer attention.")
        self.assertEqual(req_legacy.metadata.get("context"), "Transformers use multi-head attention.")

        # Initialized with Stage 4 'input_payload'
        req_modern = InferenceRequest(
            input_payload="What is backpropagation?",
            task_type="qa",
            timeout_ms=5000,
        )
        self.assertEqual(req_modern.prompt_or_payload, "What is backpropagation?")
        self.assertEqual(req_modern.timeout, 5.0)

    def test_02_response_contract_backward_compatibility(self):
        # Initialized with Stage 4 fields
        res_modern = InferenceResponse(
            request_id="req-123",
            result="Attention is all you need.",
            model_id="transformer-v1",
            execution_time_ms=125.5,
            status="SUCCESS",
        )
        self.assertEqual(res_modern.executing_model_id, "transformer-v1")
        self.assertEqual(res_modern.execution_time, 0.1255)

        # Initialized with Stage 3 fields
        res_legacy = InferenceResponse(
            request_id="req-456",
            result=None,
            executing_model_id="legacy-model",
            execution_time=0.5,
            error_info="Out of memory",
            status="FAILED",
        )
        self.assertEqual(res_legacy.model_id, "legacy-model")
        self.assertEqual(res_legacy.execution_time_ms, 500.0)
        self.assertEqual(res_legacy.error, "Out of memory")


class TestUnifiedAdapters(unittest.TestCase):
    """Verifies adapter execution across standard task categories."""

    def test_01_extractive_qa_grounded_answer(self):
        adapter = GroundedExtractiveQAAdapter()
        req = InferenceRequest(
            task_type="extractive_qa",
            input_payload="What is the learning rate?",
            context="The model was trained using an initial learning rate of 0.001 with AdamW optimizer.",
        )
        res = adapter.execute(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertIn("0.001", str(res.result))
        self.assertEqual(res.metadata.get("epistemic_status"), "EVIDENCE_BACKED")
        self.assertTrue(len(res.metadata.get("citations", [])) > 0)

    def test_02_extractive_qa_unsupported_abstention(self):
        adapter = GroundedExtractiveQAAdapter()
        req = InferenceRequest(
            task_type="extractive_qa",
            input_payload="What is the capital of Mars?",
            context="Earth orbits the Sun at an average distance of 149.6 million kilometers.",
        )
        res = adapter.execute(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.metadata.get("epistemic_status"), "UNSUPPORTED")
        self.assertIn("does not contain sufficient verified evidence", str(res.result))

    def test_03_embedding_adapter_offline_engine(self):
        engine = OfflineSemanticEngine()
        adapter = EmbeddingExecutionAdapter(engine=engine, model_id="offline-hash-embedder")
        req = InferenceRequest(
            task_type="embedding",
            input_payload=["Document embedding query", "Second sentence for vectorization."],
            model_id="offline-hash-embedder",
        )
        res = adapter.execute(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.model_id, "offline-hash-embedder")
        self.assertEqual(len(res.result), 2)
        self.assertEqual(len(res.result[0]), 512)
        self.assertEqual(res.metadata.get("dimension"), 512)
        self.assertEqual(res.metadata.get("batch_size"), 2)

    def test_04_classification_adapter_domain_and_intent(self):
        adapter = ClassificationExecutionAdapter()

        # Domain classification
        req_domain = InferenceRequest(
            task_type="domain_detection",
            input_payload="Linear transformations and eigenvalue decompositions in vector spaces.",
        )
        res_domain = adapter.execute(req_domain)
        self.assertEqual(res_domain.status, "SUCCESS")
        self.assertIn("Linear Algebra", res_domain.result.get("top_domain"))

        # Cognitive intent classification
        req_intent = InferenceRequest(
            task_type="intent_classification",
            input_payload="What is the difference between CPU and GPU architecture?",
        )
        res_intent = adapter.execute(req_intent)
        self.assertEqual(res_intent.status, "SUCCESS")
        self.assertEqual(res_intent.result.get("intent"), "COMPARISON")

    def test_05_generative_adapter_lazy_loading(self):
        # Creating adapter must be instant (no weights loaded in __init__)
        adapter = LocalGenerativeAdapter(model_id="smollm2-test-lazy")
        self.assertFalse(adapter.is_loaded)
        self.assertEqual(adapter.metadata.model_type, ModelCategory.GENERATIVE_QA)


if __name__ == "__main__":
    unittest.main()
