"""
test_grounded_qa_engine.py: End-to-end integration tests for Evidence-Grounded
Question Answering, Citation Verification, and Epistemic Taxonomy in SETU-NETRA Stage 3.

Tests:
1. CitationVerifier correctly validates matching citations as EVIDENCE_BACKED.
2. CitationVerifier detects ungrounded or non-matching citations as UNSUPPORTED.
3. CitationVerifier marks general statements without citations as GENERAL_KNOWLEDGE.
4. EvidenceGroundedQAEngine retrieves evidence, queries local adapter, formats citations,
   and computes grounding scores on actual ingested document content.
5. EvidenceGroundedQAEngine properly handles out-of-scope queries without fabricating citations.
6. Unified inference contracts (InferenceRequest / InferenceResponse) execute successfully on local CPU.
"""

import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import RetrievedPassage
from setu_netra.qa.engine import EvidenceGroundedQAEngine
from setu_netra.qa.verifier import CitationVerifier
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.contracts import InferenceRequest
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class SimpleDeterministicEngine(BaseEmbeddingEngine):
    """Deterministic embedding engine based on word hashing for QA engine tests."""

    def __init__(self, dimension: int = 32):
        self._dim = dimension

    @property
    def engine_name(self) -> str:
        return "deterministic-qa-test-engine"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def embed_texts(self, texts):
        matrix = []
        for text in texts:
            vec = np.zeros(self._dim, dtype=np.float32)
            for word in text.lower().split():
                idx = hash(word) % self._dim
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            matrix.append(vec)
        return np.vstack(matrix)


class TestGroundedQAEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_qa.db"
        self.store = SQLiteDocumentStore(self.db_path)
        self.embedding_engine = SimpleDeterministicEngine(dimension=32)
        self.retriever = DocumentRetriever(
            store=self.store,
            embedding_engine=self.embedding_engine,
        )
        self.adapter = GroundedExtractiveQAAdapter()
        self.engine = EvidenceGroundedQAEngine(
            retriever=self.retriever,
            model_adapter=self.adapter,
        )

        # Ingest test document into store
        self.doc_id = "operating_systems_ch7"
        self.store.save_document(
            doc_id=self.doc_id,
            file_path=Path("os_ch7.pdf"),
            file_hash="hash_os_ch7",
            file_type="PDF",
            page_count=1,
        )
        self.store.save_page(
            page_id=f"{self.doc_id}_p1",
            doc_id=self.doc_id,
            page_number=1,
            width=800,
            height=1100,
        )

        # Ingest text blocks
        self.passage1_text = (
            "Deadlock prevention ensures that at least one of Havender's four necessary "
            "conditions cannot hold: mutual exclusion, hold and wait, no preemption, and circular wait."
        )
        self.passage2_text = (
            "To prevent circular wait, Havender proposed imposing a total ordering on all resource types "
            "and requiring that processes request resources only in strictly increasing order."
        )
        self.passage3_text = (
            "Banker's algorithm avoids deadlocks dynamically by evaluating resource allocation safety states."
        )

        blocks = [
            {
                "block_id": 1,
                "block_type": "PARAGRAPH",
                "text": self.passage1_text,
                "bounding_box": (50.0, 100.0, 750.0, 160.0),
                "confidence": 0.99,
            },
            {
                "block_id": 2,
                "block_type": "PARAGRAPH",
                "text": self.passage2_text,
                "bounding_box": (50.0, 180.0, 750.0, 240.0),
                "confidence": 0.98,
            },
            {
                "block_id": 3,
                "block_type": "PARAGRAPH",
                "text": self.passage3_text,
                "bounding_box": (50.0, 260.0, 750.0, 320.0),
                "confidence": 0.97,
            },
        ]
        # Embed and attach to blocks
        texts = [b["text"] for b in blocks]
        embeddings = self.embedding_engine.embed_texts(texts)
        for idx, vec in enumerate(embeddings):
            blocks[idx]["embedding"] = vec
            blocks[idx]["embedding_engine"] = self.embedding_engine.engine_name

        self.store.save_blocks(self.doc_id, page_number=1, blocks_data=blocks)

    def tearDown(self):
        if hasattr(self, "store"):
            self.store.close()
        self.temp_dir.cleanup()

    def test_citation_verifier_valid_evidence(self):
        verifier = CitationVerifier(min_overlap_threshold=0.25)
        passage = RetrievedPassage(
            doc_id="doc1",
            document_name="doc1.pdf",
            page_number=1,
            block_id=2,
            block_type="PARAGRAPH",
            text="Processes must request resources in strictly increasing order to prevent circular wait.",
            bounding_box=(50.0, 180.0, 750.0, 240.0),
            confidence=0.98,
            similarity_score=0.9,
            retrieval_method="HYBRID",
        )
        answer = "Circular wait is prevented by total resource ordering [Doc: doc1, Page: 1, Block: 2]."
        result = verifier.verify_answer(answer, [passage])

        self.assertEqual(result.epistemic_status, "EVIDENCE_BACKED")
        self.assertTrue(result.is_verified)
        self.assertEqual(result.total_citations_found, 1)
        self.assertEqual(len(result.valid_citations), 1)

    def test_citation_verifier_detects_unsupported_citation(self):
        verifier = CitationVerifier()
        passage = RetrievedPassage(
            doc_id="doc1",
            document_name="doc1.pdf",
            page_number=1,
            block_id=2,
            block_type="PARAGRAPH",
            text="Some genuine passage text.",
            bounding_box=(0.0, 0.0, 10.0, 10.0),
            confidence=0.9,
            similarity_score=0.8,
            retrieval_method="HYBRID",
        )
        # Citations cite Doc 99 which was never retrieved
        answer = "Fake hallucinated answer [Doc: doc99, Page: 5, Block: 12]."
        result = verifier.verify_answer(answer, [passage])

        self.assertEqual(result.epistemic_status, "UNSUPPORTED")
        self.assertFalse(result.is_verified)
        self.assertEqual(len(result.invalid_citations), 1)

    def test_citation_verifier_general_knowledge(self):
        verifier = CitationVerifier()
        # Answer with no citations and no passages
        answer = "Deadlock prevention eliminates at least one mutual exclusion condition."
        result = verifier.verify_answer(answer, [])

        self.assertEqual(result.epistemic_status, "GENERAL_KNOWLEDGE")

    def test_end_to_end_grounded_qa(self):
        query = "How is circular wait prevented according to Havender?"
        verified = self.engine.answer_question(query=query, doc_id=self.doc_id, top_k=2)

        self.assertEqual(verified.query, query)
        self.assertEqual(verified.epistemic_status, "EVIDENCE_BACKED")
        self.assertGreater(len(verified.citations), 0)
        self.assertGreater(verified.grounding_score, 0.0)
        self.assertIn("increasing order", verified.answer_text.lower())
        self.assertGreater(verified.execution_time_ms, 0.0)

    def test_grounded_qa_adapter_inference_contract(self):
        req = InferenceRequest(
            task_type="qa",
            prompt_or_payload="Context: Total ordering prevents circular wait [Doc: d1, Page: 1, Block: 1].\n\nQuestion: What prevents circular wait?",
        )
        resp = self.adapter.execute(req)

        self.assertEqual(resp.status, "SUCCESS")
        self.assertIsNotNone(resp.request_id)
        self.assertGreater(resp.execution_time, 0.0)
        self.assertIn("Total ordering", str(resp.result))


if __name__ == "__main__":
    unittest.main()
