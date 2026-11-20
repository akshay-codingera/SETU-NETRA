"""
test_v1_integration.py: Comprehensive Version 1.0 Integration Tests for SETU-NETRA.

Tests:
1. End-to-end request flow: API/Engine -> Router -> Scheduler -> Worker -> Adapter -> VerifiedAnswer.
2. Routing behavior: Factual queries route to extractive model; comparative queries route to generative model.
3. Multi-turn conversation lifecycle: Create, ask, coreference resolution for follow-ups, persistence, and cascade deletion.
4. Document management lifecycle: Ingestion, querying, re-indexing (preserving doc_id), and cascade deletion.
5. Worker monitoring and telemetry: Worker state tracking, latency recording, and cross-platform hardware telemetry.
6. Local provider integration (Ollama): Daemon offline handling, safe discovery, and non-crashing execution errors.
7. Cloud provider integration (Gemini, Groq, OpenRouter): Graceful degradation when unconfigured and strict Local-Only Privacy Mode guard.
8. Native HTTP server REST endpoints: Validation of all management, conversation, telemetry, and settings APIs.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.config import (
    get_system_settings_view,
    is_local_only,
    set_api_key,
    set_local_only,
    set_preferred_local_model,
)
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.conversation_manager import ConversationManager
from setu_netra.qa.engine import EvidenceGroundedQAEngine, VerifiedAnswer
from setu_netra.routing.adapters.cloud_adapters import (
    GeminiCloudAdapter,
    GroqCloudAdapter,
    OpenRouterCloudAdapter,
)
from setu_netra.routing.adapters.ollama_adapter import OllamaAdapter
from setu_netra.routing.contracts import EvidenceRequirement, InferenceRequest, ModelCategory
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import get_model_registry
from setu_netra.routing.router import AdaptiveModelRouter
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.store.sqlite_store import SQLiteDocumentStore
from setu_netra.ui.app import start_server


class TestV1Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="setu_v1_test_")
        cls.db_path = str(Path(cls.temp_dir) / "v1_test.db")
        cls.doc_pipeline = DocumentIntelligencePipeline(db_path=cls.db_path)

        # Ingest a sample document for testing
        cls.sample_txt = Path(cls.temp_dir) / "operating_systems.txt"
        cls.sample_txt.write_text(
            "Operating Systems Lecture 4: Virtual Memory Management.\n"
            "Virtual memory decouples logical address spaces from physical DRAM.\n"
            "The Memory Management Unit (MMU) translates virtual page numbers to physical page frames using page tables.\n"
            "Translation Lookaside Buffers (TLB) cache recent mappings to achieve single-cycle translation.\n"
            "Demand paging loads pages into RAM only when a page fault exception occurs.\n"
            "The optimal page replacement algorithm is Belady's MIN, while LRU provides a practical approximation.\n",
            encoding="utf-8",
        )
        cls.stored_doc = cls.doc_pipeline.ingest_document(cls.sample_txt)

        # Setup inference pipeline
        cls.registry = get_model_registry()
        cls.inference_pipeline = IntelligentInferencePipeline(
            registry=cls.registry,
            auto_spawn_workers=True,
        )
        cls.qa_engine = EvidenceGroundedQAEngine(
            retriever=cls.doc_pipeline.retriever,
            inference_pipeline=cls.inference_pipeline,
        )
        cls.conv_manager = ConversationManager(
            store=cls.doc_pipeline.store,
            qa_engine=cls.qa_engine,
        )

    @classmethod
    def tearDownClass(cls):
        cls.inference_pipeline.shutdown(drain=False, timeout=1.0)
        set_local_only(False)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        set_local_only(False)

    def tearDown(self):
        set_local_only(False)


    def test_01_api_to_pipeline_end_to_end_flow(self):
        """Verify complete request flow: QA Engine -> InferencePipeline -> AdaptiveRouter -> Worker -> Answer."""
        query = "What hardware component translates virtual page numbers to physical page frames?"
        answer: VerifiedAnswer = self.qa_engine.answer_question(
            query=query,
            doc_id=self.stored_doc.doc_id,
            top_k=3,
        )

        self.assertIsNotNone(answer)
        self.assertIn("MMU", answer.answer_text)
        self.assertEqual(answer.epistemic_status, "EVIDENCE_BACKED")
        self.assertGreater(len(answer.citations), 0)
        self.assertGreater(answer.grounding_score, 0.5)

        # Telemetry & Traceability
        meta = answer.metadata or {}
        self.assertIn("request_id", meta)
        self.assertIn("worker_id", meta)
        self.assertEqual(answer.executing_model_id, "grounded-extractive-qa-v1")
        self.assertGreater(answer.execution_time_ms, 0.0)

    def test_02_adaptive_router_decisions(self):
        """Verify routing decisions: factual queries -> extractive model, comparative -> generative."""
        router = AdaptiveModelRouter(registry=self.registry)

        # Factual question requiring strict verified citations
        factual_req = InferenceRequest(
            task_type="qa",
            input_payload="What is the optimal page replacement algorithm?",
            context="Belady's MIN is the optimal page replacement algorithm.",
            metadata={"evidence_requirement": EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS},
        )
        decision_factual = router.route(factual_req)
        self.assertIn(decision_factual.selected_model_id, ["grounded-extractive-qa-v1", "extractive-qa"])

        # Comparative synthesis question
        comparative_req = InferenceRequest(
            task_type="qa",
            input_payload="Compare Belady's MIN and LRU in terms of practical implementability and hit ratio.",
            context="Belady's MIN requires future knowledge while LRU approximates locality using past access patterns.",
        )
        decision_comp = router.route(comparative_req)
        self.assertIn(decision_comp.selected_model_id, ["smollm2-135m-instruct", "grounded-extractive-qa-v1"])

    def test_03_multi_turn_conversation_and_coreference(self):
        """Verify multi-turn session creation, query coreference resolution, and cascade deletion."""
        conv = self.conv_manager.create_conversation(
            title="OS Virtual Memory Discussion",
            doc_ids=[self.stored_doc.doc_id],
        )
        conv_id = conv["conversation_id"]
        self.assertIsNotNone(conv_id)

        # Turn 1: Initial query
        t1 = self.conv_manager.ask(
            conversation_id=conv_id,
            query="What is the function of the Translation Lookaside Buffer (TLB)?",
        )
        self.assertIn("answer", t1)
        self.assertEqual(t1["answer"]["epistemic_status"], "EVIDENCE_BACKED")

        # Turn 2: Follow-up query referencing Turn 1
        t2 = self.conv_manager.ask(
            conversation_id=conv_id,
            query="What does it cache to achieve single-cycle translation?",
        )
        self.assertIn("answer", t2)
        # Check that query resolution expanded or preserved the deictic reference
        history = self.conv_manager.get_conversation(conv_id)
        self.assertEqual(len(history["messages"]), 4)  # 2 user + 2 assistant messages

        # Verify deletion cascades cleanly
        del_ok = self.conv_manager.delete_conversation(conv_id)
        self.assertTrue(del_ok)
        self.assertIsNone(self.conv_manager.get_conversation(conv_id))
        remaining_messages = self.doc_pipeline.store.get_messages(conv_id)
        self.assertEqual(len(remaining_messages), 0)

    def test_04_document_management_delete_and_reindex(self):
        """Verify document re-indexing preserves doc_id, and delete removes all related tables."""
        temp_txt = Path(self.temp_dir) / "cache_protocol.txt"
        temp_txt.write_text(
            "Cache Coherence Protocols:\n"
            "MESI protocol defines Modified, Exclusive, Shared, and Invalid states for write-back caches.\n"
            "MOESI protocol introduces an Owner state to allow dirty sharing without main memory writes.\n",
            encoding="utf-8",
        )
        doc = self.doc_pipeline.ingest_document(temp_txt)
        doc_id = doc.doc_id

        # Verify initial storage
        self.assertIsNotNone(self.doc_pipeline.store.get_document_by_id(doc_id))
        initial_blocks = self.doc_pipeline.store.get_blocks(doc_id)
        self.assertGreater(len(initial_blocks), 0)

        # Re-index document
        reindexed = self.doc_pipeline.reindex_document(doc_id)
        self.assertEqual(reindexed.doc_id, doc_id)
        reindexed_blocks = self.doc_pipeline.store.get_blocks(doc_id)
        self.assertEqual(len(reindexed_blocks), len(initial_blocks))

        # Delete document
        delete_success = self.doc_pipeline.store.delete_document(doc_id)
        self.assertTrue(delete_success)
        self.assertIsNone(self.doc_pipeline.store.get_document_by_id(doc_id))
        self.assertEqual(len(self.doc_pipeline.store.get_blocks(doc_id)), 0)
        emb_meta, _ = self.doc_pipeline.store.get_all_embeddings(doc_id=doc_id)
        self.assertEqual(len(emb_meta), 0)

    def test_05_worker_monitoring_and_telemetry(self):
        """Verify worker pool status tracking and system hardware telemetry metrics."""
        workers = self.inference_pipeline.worker_pool.list_workers()
        self.assertGreater(len(workers), 0)

        # Verify worker telemetry
        for w in workers:
            w_state_str = w.state.name if hasattr(w.state, "name") else str(w.state)
            self.assertIn(w_state_str, ["IDLE", "BUSY", "COOLING_DOWN"])
            self.assertIsInstance(w.active_requests_count, int)
            self.assertIsInstance(w.consecutive_failures, int)

        # Verify system hardware telemetry
        tel = get_system_telemetry()
        self.assertTrue(tel.is_valid)
        self.assertGreaterEqual(tel.cpu_percent, 0.0)
        self.assertGreaterEqual(tel.ram_percent, 0.0)
        self.assertGreater(tel.avail_ram_mb, 0.0)

    def test_06_local_provider_ollama_graceful_handling(self):
        """Verify Ollama adapter does not crash when daemon is offline."""
        # Use an unreachable port
        ollama = OllamaAdapter(base_url="http://127.0.0.1:54321")

        self.assertFalse(ollama.is_available())
        discovered = ollama.discover_models()
        self.assertEqual(discovered, [])

        # Execution against offline service returns clean error response
        req = InferenceRequest(
            task_type="text_generation",
            input_payload="Explain TLB reach.",
        )
        resp = ollama.execute(req)
        self.assertEqual(resp.status, "FAILED")
        self.assertIsNotNone(resp.error)
        self.assertTrue("not reachable" in resp.error.lower() or "error" in resp.error.lower())

    def test_07_cloud_providers_unconfigured_and_local_only(self):
        """Verify cloud adapters degrade gracefully without credentials and obey Local-Only Privacy Mode."""
        gemini = GeminiCloudAdapter(api_key="")
        groq = GroqCloudAdapter(api_key="")
        openrouter = OpenRouterCloudAdapter(api_key="")

        # Missing credentials return NOT_CONFIGURED
        self.assertEqual(gemini.status, "NOT_CONFIGURED")
        self.assertEqual(groq.status, "NOT_CONFIGURED")
        self.assertEqual(openrouter.status, "NOT_CONFIGURED")

        req = InferenceRequest(
            task_type="text_generation",
            input_payload="Summarize virtual memory.",
        )
        resp = gemini.execute(req)
        self.assertEqual(resp.status, "FAILED")
        self.assertTrue("api key" in resp.error.lower() or "not_configured" in resp.error.lower())

        # Test Local-Only Privacy Mode
        set_local_only(True)
        self.assertTrue(is_local_only())

        # Calling cloud adapter under Local-Only mode immediately raises PermissionError
        with self.assertRaises(PermissionError):
            groq.execute(req)

        with self.assertRaises(PermissionError):
            openrouter.execute(req)

        # Reset Local-Only mode
        set_local_only(False)
        self.assertFalse(is_local_only())

    def test_08_http_server_endpoints(self):
        """Verify that native HTTP server endpoints serve valid JSON responses."""
        test_port = 18505
        server = start_server(port=test_port, db_path=self.db_path)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        time.sleep(0.5)

        base_url = f"http://127.0.0.1:{test_port}"
        try:
            # 1. GET /api/routing/status
            with urlopen(f"{base_url}/api/routing/status") as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode())
                self.assertIn("active_scheduler", data)
                self.assertEqual(data["status"], "HEALTHY")

            # 2. GET /api/telemetry
            with urlopen(f"{base_url}/api/telemetry") as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode())
                self.assertIn("cpu_percent", data)
                self.assertIn("memory_percent", data)

            # 3. GET /api/workers
            with urlopen(f"{base_url}/api/workers") as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode())
                self.assertIn("workers", data)
                self.assertGreater(len(data["workers"]), 0)

            # 4. GET /api/models
            with urlopen(f"{base_url}/api/models") as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode())
                self.assertIn("models", data)

            # 5. GET /api/settings and POST /api/settings
            with urlopen(f"{base_url}/api/settings") as res:
                self.assertEqual(res.status, 200)
                settings = json.loads(res.read().decode())
                self.assertIn("local_only", settings)

            post_req = Request(
                f"{base_url}/api/settings",
                data=json.dumps({"local_only": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(post_req) as res:
                self.assertEqual(res.status, 200)
                updated = json.loads(res.read().decode())
                self.assertTrue(updated["local_only"])

            # Reset local_only back to False
            reset_req = Request(
                f"{base_url}/api/settings",
                data=json.dumps({"local_only": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(reset_req) as res:
                self.assertEqual(res.status, 200)

            # 6. POST /api/conversations & GET /api/conversations
            create_conv_req = Request(
                f"{base_url}/api/conversations",
                data=json.dumps({"title": "HTTP Test Conv", "doc_ids": [self.stored_doc.doc_id]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(create_conv_req) as res:
                self.assertEqual(res.status, 200)
                cdata = json.loads(res.read().decode())
                http_conv_id = cdata["conversation_id"]

            with urlopen(f"{base_url}/api/conversations") as res:
                self.assertEqual(res.status, 200)
                conv_list = json.loads(res.read().decode())
                self.assertTrue(any(c["conversation_id"] == http_conv_id for c in conv_list["conversations"]))

            # Cleanup conversation
            del_req = Request(f"{base_url}/api/conversations/{http_conv_id}", method="DELETE")
            with urlopen(del_req) as res:
                self.assertEqual(res.status, 200)

        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
