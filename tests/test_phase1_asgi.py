"""
test_phase1_asgi.py: Comprehensive test suite for Phase 1 Additive ASGI Engine & Core EventBus.

Tests:
1. FastAPI app startup and root endpoint.
2. GET /api/v1/health response schema and status.
3. Correlation ID middleware generation and propagation.
4. RFC 9457 Problem Details error responses (422 and custom exceptions).
5. EventBus atomic publication, ordering, and monotonic sequence IDs.
6. EventBus 2048-event ring buffer and Last-Event-ID replay.
7. EventBus SSE formatting and heartbeat messages.
8. Slow-subscriber backpressure mitigation and queue frame dropping.
9. Graceful client disconnection and subscriber cleanup.
10. Async bounded thread execution via CapacityLimiter.
11. Ollama model concurrency semaphore preservation.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.api.event_bus import EventBus, get_event_bus
from setu_netra.api.main import create_app
from setu_netra.api.pipeline_adapter import AsyncPipelineAdapter
from setu_netra.api.schemas import TelemetryEvent


class TestPhase1ASGIEngine(unittest.TestCase):
    """Unit and integration test cases for Phase 1 ASGI Engine."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = "output/test_phase1.db"
        cls.app = create_app(db_path=cls.db_path)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        # Cleanup test db
        for ext in ["", "-wal", "-shm"]:
            p = Path(f"{cls.db_path}{ext}")
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_01_app_startup_and_root(self):
        """Verify ASGI server initializes, mounts routers, and root returns 200."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["version"], "2.0.0-RC1")
        self.assertEqual(data["status"], "OPERATIONAL")
        self.assertIn("health_url", data)
        self.assertIn("events_stream_url", data)

    def test_02_health_endpoint(self):
        """Verify GET /api/v1/health returns structured operational health."""
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ["HEALTHY", "DEGRADED", "UNHEALTHY"])
        self.assertEqual(data["version"], "2.0.0-RC1")
        self.assertIn("database", data)
        self.assertTrue(data["database"].get("connected"))
        self.assertIn("ollama", data)
        self.assertIn("worker_pool", data)
        self.assertIn("hardware", data)
        self.assertGreaterEqual(data["uptime_seconds"], 0.0)

    def test_03_correlation_id_propagation(self):
        """Verify X-Correlation-ID is preserved if provided, or generated if absent."""
        # Case A: Client provides correlation ID
        custom_corr = "corr_custom_test_12345"
        resp_a = self.client.get("/api/v1/health", headers={"X-Correlation-ID": custom_corr})
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a.headers.get("X-Correlation-ID"), custom_corr)

        # Case B: Server generates correlation ID
        resp_b = self.client.get("/api/v1/health")
        self.assertEqual(resp_b.status_code, 200)
        corr_id = resp_b.headers.get("X-Correlation-ID")
        self.assertIsNotNone(corr_id)
        self.assertTrue(corr_id.startswith("corr_"))

    def test_04_rfc_9457_validation_error(self):
        """Verify input validation failures return RFC 9457 Problem Details format."""
        # Empty query string violates min_length=1
        resp = self.client.post("/api/v1/query", json={"query": ""})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.headers.get("Content-Type"), "application/problem+json")
        
        data = resp.json()
        self.assertEqual(data["type"], "https://setu-netra.internal/errors/VALIDATION_ERROR")
        self.assertEqual(data["status"], 422)
        self.assertEqual(data["title"], "Unprocessable Entity")
        self.assertIn("invalid_params", data)
        self.assertTrue(len(data["invalid_params"]) > 0)
        self.assertIsNotNone(data.get("correlation_id"))
        self.assertIsNotNone(data.get("timestamp"))

    def test_05_event_bus_publication_and_ordering(self):
        """Verify EventBus assigns atomic monotonically increasing sequence IDs."""
        bus = EventBus(replay_buffer_size=100)
        events = []
        for i in range(10):
            ev = bus.publish(
                event_type="TEST_TICK",
                source_subsystem="UnitTest",
                payload={"index": i},
                correlation_id=f"corr_test_{i}",
            )
            events.append(ev)

        # Sequence IDs must be strictly increasing
        for idx in range(len(events) - 1):
            self.assertEqual(events[idx + 1].event_id, events[idx].event_id + 1)
            self.assertGreater(events[idx + 1].timestamp_ns, 0)
            self.assertIn("T", events[idx + 1].timestamp_iso)

    def test_06_event_bus_2048_buffer_and_replay(self):
        """Verify circular ring buffer retains events and accurately replays by Last-Event-ID."""
        bus = EventBus(replay_buffer_size=2048)
        
        # Publish 30 events
        for i in range(1, 31):
            bus.publish(
                event_type="DATA_PACKET",
                source_subsystem="BufferTest",
                payload={"val": i},
                correlation_id="corr_buffer_test",
            )

        # Retrieve events after event_id=25 (should yield 26, 27, 28, 29, 30)
        replayed = bus.get_retained_events(after_event_id=25)
        self.assertEqual(len(replayed), 5)
        self.assertEqual([e.event_id for e in replayed], [26, 27, 28, 29, 30])

    def test_07_event_bus_slow_subscriber_handling(self):
        """Verify slow client with full queue does not block publisher and receives warning."""
        bus = EventBus(replay_buffer_size=100, subscriber_queue_size=4)

        # Register a subscriber queue directly
        sub_queue = asyncio.Queue(maxsize=4)
        bus._subscribers["sub_slow_test"] = sub_queue

        # Publish 8 events without reading from sub_queue
        for i in range(8):
            bus.publish(
                event_type="BURST_EVENT",
                source_subsystem="BurstTest",
                payload={"i": i},
                correlation_id="corr_slow_client",
            )

        # The queue must not exceed maxsize and must contain CLIENT_BACKPRESSURE_WARNING
        self.assertLessEqual(sub_queue.qsize(), 4)
        
        event_types = []
        while not sub_queue.empty():
            ev = sub_queue.get_nowait()
            event_types.append(ev.event_type)

        self.assertIn("CLIENT_BACKPRESSURE_WARNING", event_types)
        bus.stop()

    def test_08_event_bus_sse_formatting(self):
        """Verify TelemetryEvent serialization strictly conforms to SSE text/event-stream."""
        bus = EventBus()
        ev = bus.create_event(
            event_type="ROUTER_DECISION",
            source_subsystem="AdaptiveRouter",
            payload={"selected_model": "ollama/qwen3.5:2b"},
            correlation_id="corr_format_test",
        )
        sse_str = bus.format_sse(ev)
        
        lines = sse_str.strip().split("\n")
        self.assertTrue(lines[0].startswith("id: "))
        self.assertEqual(lines[1], "event: ROUTER_DECISION")
        self.assertTrue(lines[2].startswith("data: {"))

    def test_09_last_event_id_reconnection_stream(self):
        """Verify async subscribe generator yields replayed historical events first."""
        async def _run():
            bus = EventBus(replay_buffer_size=50)
            loop = asyncio.get_running_loop()
            bus.bind_loop(loop)

            # Pre-populate 5 events
            for i in range(1, 6):
                bus.publish(
                    event_type="STREAM_STEP",
                    source_subsystem="StreamTest",
                    payload={"step": i},
                    correlation_id="corr_stream_test",
                )

            # Subscribe with last_event_id=3
            chunks = []
            gen = bus.subscribe(sub_id="sub_test_stream", last_event_id=3)
            
            # Read 2 replayed chunks (events 4 and 5)
            c1 = await gen.__anext__()
            c2 = await gen.__anext__()
            chunks.extend([c1, c2])

            self.assertIn("id: 4", c1)
            self.assertIn("id: 5", c2)
            
            # Clean up generator
            await gen.aclose()
            bus.stop()

        asyncio.run(_run())

    def test_10_capacity_limiter_thread_dispatch(self):
        """Verify AsyncPipelineAdapter dispatches execution into bounded thread pool."""
        async def _run():
            from setu_netra.api.pipeline_adapter import AsyncPipelineAdapter
            from unittest.mock import MagicMock
            from setu_netra.qa.engine import VerifiedAnswer

            mock_qa = MagicMock()
            mock_qa.answer_question.return_value = VerifiedAnswer(
                query="Test question?",
                answer_text="Verified test answer.",
                epistemic_status="EVIDENCE_BACKED",
                citations=[],
                grounding_score=0.92,
                retrieved_passages=[],
                executing_model_id="grounded-extractive-qa-v1",
                execution_time_ms=1.5,
                explanation="Grounded in evidence.",
                metadata={"worker_id": "extractive_w1"},
            )
            mock_pipe = MagicMock()
            bus = EventBus()
            loop = asyncio.get_running_loop()
            bus.bind_loop(loop)

            adapter = AsyncPipelineAdapter(
                qa_engine=mock_qa,
                inference_pipeline=mock_pipe,
                event_bus=bus,
                max_concurrent_threads=2,
            )
            
            self.assertEqual(adapter.capacity_limiter.total_tokens, 2)

            # Execute query through adapter
            result = await adapter.answer_question(
                query="What is the capital?",
                correlation_id="corr_unit_test",
            )
            self.assertEqual(result["answer_text"], "Verified test answer.")
            self.assertEqual(result["epistemic_status"], "EVIDENCE_BACKED")
            self.assertEqual(result["correlation_id"], "corr_unit_test")
            self.assertEqual(mock_qa.answer_question.call_count, 1)

            # Check that ingress and egress events were published
            events = bus.get_retained_events()
            event_types = [e.event_type for e in events]
            self.assertIn("REQUEST_INGRESS", event_types)
            self.assertIn("VERIFIER_TAXONOMY", event_types)
            self.assertIn("EGRESS_COMPLETED", event_types)

            bus.stop()

        asyncio.run(_run())

    def test_11_ollama_concurrency_semaphore_preservation(self):
        """Verify that OllamaProviderAdapter concurrency lock is preserved."""
        from setu_netra.routing.adapters.ollama_adapter import (
            OllamaProviderAdapter,
            _OLLAMA_CONCURRENCY_SEMAPHORE,
        )

        # Global semaphore must be initialized with a bound of 1
        self.assertIsNotNone(_OLLAMA_CONCURRENCY_SEMAPHORE)
        
        # Test acquiring and releasing the semaphore
        acquired = _OLLAMA_CONCURRENCY_SEMAPHORE.acquire(timeout=1.0)
        self.assertTrue(acquired)
        try:
            # Second acquire with 0 timeout must fail (concurrency ceiling = 1)
            second_acquire = _OLLAMA_CONCURRENCY_SEMAPHORE.acquire(timeout=0.01)
            self.assertFalse(second_acquire)
        finally:
            _OLLAMA_CONCURRENCY_SEMAPHORE.release()


if __name__ == "__main__":
    unittest.main()
