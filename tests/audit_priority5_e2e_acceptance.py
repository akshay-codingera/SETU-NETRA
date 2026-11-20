"""
tests/audit_priority5_e2e_acceptance.py

End-to-End Acceptance Test Suite for SETU-NETRA V1.1.0 (Priority 5).
Executes a rigorous 10-step sequence on a real multi-page PDF document:
1. Multi-Page Document Ingestion (pypdfium2 rasterization).
2. Layout Reconstruction & Spatial Bounding Box Indexing.
3. Question Extraction & Intent Classification.
4. Multi-Passage Hybrid Retrieval (FTS Lexical + Dense Embeddings).
5. Contradictory Evidence & Negation Verification.
6. Citation Spatial Bounds Mapping.
7. Grounded Extractive QA with Provenance Verification.
8. Generative SLM Synthesis (Ollama Qwen 3.5 2B CPU inference).
9. Dynamic Adaptive Router Intent Dispatching & Worker Scheduling Under Load.
10. Strict Local-Only Zero-Egress Boundary Verification.
"""

import json
import os
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from setu_netra.core.config import is_local_only, set_local_only
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.engine import EvidenceGroundedQAEngine
from setu_netra.qa.question_extractor import QuestionExtractor
from setu_netra.routing.contracts import InferenceRequest
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.router import AdaptiveModelRouter
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class SocketOutboundRecorder:
    def __init__(self):
        self.connections = []
        self._orig_connect = socket.socket.connect

    def connect_guard(self, sock_self, address):
        host = address[0]
        self.connections.append(address)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise PermissionError(f"Local-Only Mode strictly blocked external socket to {address}")
        return self._orig_connect(sock_self, address)


class Priority5EndToEndAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "output/acceptance_test.db"
        if Path(cls.db_path).exists():
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

        cls.pdf_path = Path("output/e2e_acceptance_multipage.pdf")
        if not cls.pdf_path.exists():
            raise FileNotFoundError(f"Fixture PDF {cls.pdf_path} does not exist.")

        cls.store = SQLiteDocumentStore(db_path=cls.db_path)
        cls.doc_pipeline = DocumentIntelligencePipeline(store=cls.store, db_path=cls.db_path)
        cls.inference_pipeline = IntelligentInferencePipeline()
        cls.qa_engine = EvidenceGroundedQAEngine(
            retriever=cls.doc_pipeline.retriever,
            inference_pipeline=cls.inference_pipeline,
        )
        cls.q_extractor = QuestionExtractor()

        cls.results = {
            "steps": {},
            "verdict": "PENDING",
            "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def setUp(self):
        set_local_only(True)

    def test_01_step1_document_ingestion(self):
        """Step 1: Multi-Page Document Ingestion."""
        start = time.perf_counter()
        stored_doc = self.doc_pipeline.ingest_document(self.pdf_path)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        self.assertIsNotNone(stored_doc)
        self.assertTrue(stored_doc.doc_id.startswith("doc_"))
        self.assertEqual(stored_doc.page_count, 2, "Document must have exactly 2 pages")
        self.assertEqual(stored_doc.status, "PROCESSED")

        self.__class__.stored_doc_id = stored_doc.doc_id
        self.results["steps"]["step_01_document_ingestion"] = {
            "status": "PASS",
            "doc_id": stored_doc.doc_id,
            "page_count": stored_doc.page_count,
            "ingestion_status": stored_doc.status,
            "elapsed_ms": round(elapsed_ms, 2),
        }

    def test_02_step2_layout_reconstruction(self):
        """Step 2: Layout Reconstruction & Bounding Box Indexing."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)
        self.assertIsNotNone(doc_id)

        blocks = self.store.get_blocks(doc_id)
        self.assertGreaterEqual(len(blocks), 4, "Must have indexed at least 4 text blocks across 2 pages")

        pages_represented = set(b["page_number"] for b in blocks)
        self.assertEqual(pages_represented, {1, 2}, "Both Page 1 and Page 2 must have indexed blocks")

        for b in blocks:
            bbox = b.get("bounding_box")
            self.assertIsNotNone(bbox, f"Block {b['block_id']} must have bounding box")
            self.assertEqual(len(bbox), 4, "Bounding box must be 4-tuple (x0, y0, x1, y1)")
            x0, y0, x1, y1 = bbox
            self.assertGreaterEqual(x1, x0, "x1 must be >= x0")
            self.assertGreaterEqual(y1, y0, "y1 must be >= y0")

        self.results["steps"]["step_02_layout_reconstruction"] = {
            "status": "PASS",
            "total_blocks_indexed": len(blocks),
            "pages_indexed": sorted(list(pages_represented)),
            "bounding_boxes_validated": True,
        }

    def test_03_step3_question_extraction(self):
        """Step 3: Question Extraction & Intent Classification."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)
        blocks = self.store.get_blocks(doc_id)
        full_text = "\n\n".join(b["text"] for b in blocks)

        extracted = self.q_extractor.extract_from_raw_text(full_text)
        self.assertGreaterEqual(len(extracted), 2, "Must extract at least 2 questions from document")

        q_texts = [q.get("question", "") if isinstance(q, dict) else str(q) for q in extracted]
        found_q1 = any("tier" in q.lower() or "architecture" in q.lower() for q in q_texts)
        found_q2 = any("database" in q.lower() or "store" in q.lower() for q in q_texts)

        self.assertTrue(found_q1, f"Failed to extract Question 1 from text. Found: {q_texts}")
        self.assertTrue(found_q2, f"Failed to extract Question 2 from text. Found: {q_texts}")

        self.results["steps"]["step_03_question_extraction"] = {
            "status": "PASS",
            "extracted_count": len(extracted),
            "sample_extracted_questions": q_texts[:3],
        }

    def test_04_step4_multi_passage_retrieval(self):
        """Step 4: Multi-Passage Hybrid Retrieval."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)

        query = "What are the two primary tiers of the SETU-NETRA architecture?"
        retrieval_res = self.doc_pipeline.retriever.retrieve(query=query, doc_id=doc_id, top_k=3)

        self.assertGreaterEqual(len(retrieval_res), 1)
        found_target_passage = any("two-tier" in p.text.lower() or "router" in p.text.lower() for p in retrieval_res)
        self.assertTrue(found_target_passage, "Retrieved passages must contain the target architectural description")

        self.results["steps"]["step_04_multi_passage_retrieval"] = {
            "status": "PASS",
            "query": query,
            "top_passage_snippet": retrieval_res[0].text[:80],
            "top_passage_score": round(retrieval_res[0].similarity_score, 4),
            "retrieved_count": len(retrieval_res),
        }

    def test_05_step5_contradictory_evidence_verification(self):
        """Step 5: Contradictory Evidence & Negation Verification."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)

        query = "Does the execution engine bypass hardware telemetry verification?"
        retrieval_res = self.doc_pipeline.retriever.retrieve(query=query, doc_id=doc_id, top_k=3)

        self.assertGreaterEqual(len(retrieval_res), 1)
        found_negation = any("not bypass" in p.text.lower() for p in retrieval_res)
        self.assertTrue(found_negation, "Retrieved evidence must surface explicit negation constraint")

        self.results["steps"]["step_05_contradictory_evidence_verification"] = {
            "status": "PASS",
            "query": query,
            "negation_detected_in_evidence": True,
            "retrieved_evidence_snippet": retrieval_res[0].text[:80],
        }

    def test_06_step6_citation_spatial_bounds(self):
        """Step 6: Citation Spatial Bounds Mapping."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)
        blocks = self.store.get_blocks(doc_id)

        target_block = next(b for b in blocks if "two-tier" in b["text"].lower() or "router" in b["text"].lower())
        bbox = target_block["bounding_box"]

        # Ensure spatial bounding box conforms to [x0, y0, x1, y1] with valid width and height
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0

        self.assertGreater(width, 0.0)
        self.assertGreater(height, 0.0)
        self.assertGreater(x0, 0.0)
        self.assertGreater(y0, 0.0)

        self.results["steps"]["step_06_citation_spatial_bounds"] = {
            "status": "PASS",
            "page_num": target_block["page_number"],
            "block_id": target_block["block_id"],
            "bounding_box": bbox,
            "width": round(width, 2),
            "height": round(height, 2),
            "spatial_projection_verified": True,
        }

    def test_07_step7_grounded_extractive_qa(self):
        """Step 7: Grounded Extractive QA Generation via QA Engine."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)

        query = "What are the two primary tiers of the SETU-NETRA architecture?"
        answer = self.qa_engine.answer_question(
            query=query,
            doc_id=doc_id,
            top_k=3,
            model_id="grounded-extractive-qa-v1",
        )

        self.assertEqual(answer.epistemic_status, "EVIDENCE_BACKED")
        self.assertTrue(
            "two-tier" in answer.answer_text.lower() or "architecture" in answer.answer_text.lower(),
            f"Answer text should relate to architecture. Got: {answer.answer_text}",
        )
        self.assertGreaterEqual(len(answer.citations), 1, "Must produce at least one grounded citation")

        first_cite = answer.citations[0]
        self.assertIn("page", first_cite)
        self.assertIn("bounding_box", first_cite)

        self.results["steps"]["step_07_grounded_extractive_qa"] = {
            "status": "PASS",
            "epistemic_status": answer.epistemic_status,
            "answer_preview": answer.answer_text[:100],
            "citations_count": len(answer.citations),
            "executing_model": answer.executing_model_id,
            "execution_time_ms": answer.execution_time_ms,
        }

    def test_08_step8_generative_slm_synthesis(self):
        """Step 8: Generative SLM Answer Synthesis via Qwen 3.5 2B."""
        doc_id = getattr(self.__class__, "stored_doc_id", None)

        query = "In one concise sentence, explain the purpose of the two-tier architecture."
        answer = self.qa_engine.answer_question(
            query=query,
            doc_id=doc_id,
            top_k=3,
            model_id="ollama/qwen3.5:2b",
            think=False,
        )

        self.assertIn(answer.epistemic_status, ["EVIDENCE_BACKED", "GENERAL_KNOWLEDGE"])
        self.assertIsNotNone(answer.answer_text)
        self.assertGreater(len(answer.answer_text.strip()), 10)
        self.assertNotIn("<think>", answer.answer_text, "Thinking tags must be excluded from final answer text")

        self.results["steps"]["step_08_generative_slm_synthesis"] = {
            "status": "PASS",
            "executing_model": answer.executing_model_id,
            "execution_time_ms": answer.execution_time_ms,
            "answer_preview": answer.answer_text.strip()[:120],
            "epistemic_status": answer.epistemic_status,
        }

    def test_09_step9_adaptive_routing_and_scheduling(self):
        """Step 9: Dynamic Adaptive Router & Scheduler Dispatching Under Load."""
        router = AdaptiveModelRouter()

        # Switch pipeline scheduler to CapacityAwareScheduler
        self.inference_pipeline.set_scheduler(CapacityAwareScheduler())

        # 1. Test Factual query routing
        req_factual = InferenceRequest(
            task_type="qa",
            input_payload="What is the database engine used in SETU-NETRA?",
        )
        dec_factual = router.route(req_factual)
        self.assertIn("extractive", dec_factual.selected_model_id.lower())

        # 2. Test Complex Synthesis query routing
        req_synth = InferenceRequest(
            task_type="reasoning",
            input_payload="Compare the latency advantages of capacity-aware scheduling versus round-robin.",
        )
        dec_synth = router.route(req_synth)
        self.assertIn(dec_synth.selected_model_id, ["ollama/qwen3.5:2b", "smollm2-135m-instruct", "grounded-extractive-qa-v1"])

        # 3. Test Worker Pool status via the active inference pipeline's worker pool
        telemetry = self.inference_pipeline.worker_pool.get_pool_status()
        self.assertGreaterEqual(len(telemetry), 1)
        self.assertIn("ollama/qwen3.5:2b_w1", telemetry)

        self.results["steps"]["step_09_adaptive_routing_and_scheduling"] = {
            "status": "PASS",
            "active_scheduler": "CapacityAwareScheduler",
            "factual_routed_to": dec_factual.selected_model_id,
            "reasoning_routed_to": dec_synth.selected_model_id,
            "worker_count": len(telemetry),
        }

    def test_10_step10_local_only_boundary(self):
        """Step 10: Strict Local-Only Zero-Egress Boundary Verification."""
        self.assertTrue(is_local_only())

        recorder = SocketOutboundRecorder()
        with patch.object(socket.socket, "connect", recorder.connect_guard):
            req_cloud = InferenceRequest(
                task_type="generative_qa",
                input_payload="Explain document grounding.",
                model_id="gemini-1.5-flash",
            )
            resp = self.inference_pipeline.execute(req_cloud)

            # Pipeline should gracefully refuse cloud or failover to local model
            if resp.status == "SUCCESS":
                self.assertNotIn("gemini", resp.model_id.lower(), "Must NOT execute on cloud under local-only mode")
            else:
                self.assertIn(resp.status, ["FAILED", "REJECTED"])

        # Verify zero external socket calls occurred
        non_loopback_calls = [addr for addr in recorder.connections if addr[0] not in ("127.0.0.1", "localhost", "::1")]
        self.assertEqual(len(non_loopback_calls), 0, f"External network calls detected: {non_loopback_calls}")

        self.results["steps"]["step_10_local_only_boundary"] = {
            "status": "PASS",
            "outbound_connections_count": len(recorder.connections),
            "non_loopback_calls": len(non_loopback_calls),
            "zero_egress_verified": True,
        }

    @classmethod
    def tearDownClass(cls):
        all_passed = all(s.get("status") == "PASS" for s in cls.results["steps"].values()) and len(cls.results["steps"]) == 10
        cls.results["verdict"] = "ACCEPTED_READY_FOR_DEMO" if all_passed else "ACCEPTANCE_FAILED"

        out_path = Path("output/priority5_acceptance_results.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cls.results, f, indent=2)
        print(f"\nSaved Priority 5 End-to-End Acceptance results to {out_path}")


if __name__ == "__main__":
    unittest.main()
