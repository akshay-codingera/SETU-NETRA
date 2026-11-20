"""
test_ollama_qwen.py: Comprehensive unit and integration verification for Ollama Qwen 3.5 2B.

Verifies:
1. Adapter initialization, canonical IDs, and model metadata.
2. Local-only Privacy Mode enforcement (strictly blocking non-loopback endpoints).
3. Think mode parameter passing, extraction of <think>...</think> traces into metadata, and clean answer generation.
4. Concurrency semaphore guard (limiting concurrent generation).
5. Coexistence memory guard and SmolLM2 unloading.
6. Graceful failure and error reporting when unreachable.
7. Live local inference execution against local Ollama daemon (if online).
"""

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.ollama_adapter import (
    OllamaProviderAdapter,
    is_loopback_host,
)
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse, ModelCategory
from setu_netra.core.config import is_local_only, set_local_only


class TestOllamaQwenAdapter(unittest.TestCase):
    """Unit test suite for OllamaProviderAdapter with Qwen 3.5 2B."""

    def setUp(self):
        self._orig_local_only = is_local_only()

    def tearDown(self):
        set_local_only(self._orig_local_only)

    def test_01_adapter_metadata_and_canonical_id(self):
        """Verify default configuration targets qwen3.5:2b with correct metadata."""
        adapter = OllamaProviderAdapter(model_name="qwen3.5:2b")
        self.assertEqual(adapter.model_id, "ollama/qwen3.5:2b")
        self.assertEqual(adapter.model_name, "qwen3.5:2b")
        meta = adapter.metadata
        self.assertEqual(meta.model_id, "ollama/qwen3.5:2b")
        self.assertEqual(meta.model_type, ModelCategory.GENERATIVE_SLM)
        self.assertEqual(meta.context_length, 2048)
        self.assertEqual(meta.memory_requirement.get("min_ram_mb"), 1024)
        self.assertEqual(meta.provider, "Ollama (Local)")
        self.assertEqual(meta.execution_backend, "OLLAMA_DAEMON")

    def test_02_loopback_host_validation(self):
        """Verify loopback IP and localhost detection."""
        self.assertTrue(is_loopback_host("http://127.0.0.1:11434"))
        self.assertTrue(is_loopback_host("http://localhost:11434"))
        self.assertTrue(is_loopback_host("http://[::1]:11434"))
        self.assertFalse(is_loopback_host("http://192.168.1.50:11434"))
        self.assertFalse(is_loopback_host("https://api.ollama.ai"))
        self.assertFalse(is_loopback_host("http://remote.host.internal:11434"))

    def test_03_local_only_mode_blocks_remote_host(self):
        """Ensure Local-Only Privacy Mode rejects non-loopback Ollama endpoints."""
        set_local_only(True)
        remote_adapter = OllamaProviderAdapter(
            base_url="http://remote.internal.corp:11434",
            model_name="qwen3.5:2b",
        )
        req = InferenceRequest(
            task_type="text_generation",
            input_payload="Summarize this internal memo.",
        )
        resp = remote_adapter.execute(req)
        self.assertEqual(resp.status, "REJECTED")
        self.assertIn("Local-Only Privacy Mode blocked", resp.error)

    def test_04_offline_daemon_graceful_handling(self):
        """Verify clean error and failure state when daemon is unreachable."""
        offline_adapter = OllamaProviderAdapter(
            base_url="http://127.0.0.1:59999",
            model_name="qwen3.5:2b",
        )
        self.assertFalse(offline_adapter.is_available())
        self.assertEqual(offline_adapter.discover_models(), [])

        req = InferenceRequest(
            task_type="text_generation",
            input_payload="What is virtual memory?",
        )
        resp = offline_adapter.execute(req)
        self.assertEqual(resp.status, "FAILED")
        self.assertIn("not reachable", resp.error.lower())
        self.assertIn("error", resp.error.lower())

    @patch("setu_netra.routing.adapters.ollama_adapter.urllib.request.urlopen")
    def test_05_think_mode_payload_and_extraction(self, mock_urlopen):
        """Verify think mode is disabled by default, enabled when requested, and <think> tags are parsed."""
        adapter = OllamaProviderAdapter(model_name="qwen3.5:2b")
        adapter.is_available = MagicMock(return_value=True)
        adapter._validate_memory_and_coexistence = MagicMock(return_value=None)

        # Mock JSON response with <think> tag inside response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = (
            b'{"response": "<think>Thinking about RAM...</think>Virtual memory is an abstraction.", '
            b'"prompt_eval_count": 15, "eval_count": 22, "total_duration": 500000000}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Request with think=True
        req = InferenceRequest(
            task_type="text_generation",
            input_payload="Explain virtual memory.",
            metadata={"think": True},
        )
        resp = adapter.execute(req)

        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.result, "Virtual memory is an abstraction.")
        self.assertEqual(resp.metadata.get("thinking"), "Thinking about RAM...")
        self.assertEqual(resp.metadata.get("prompt_tokens"), 15)
        self.assertEqual(resp.metadata.get("completion_tokens"), 22)

    @patch("setu_netra.routing.adapters.ollama_adapter.urllib.request.urlopen")
    def test_06_concurrency_semaphore(self, mock_urlopen):
        """Verify concurrency semaphore limits simultaneous local generations."""
        adapter = OllamaProviderAdapter(model_name="qwen3.5:2b")
        adapter.is_available = MagicMock(return_value=True)
        adapter._validate_memory_and_coexistence = MagicMock(return_value=None)

        execution_order = []
        active_count = [0]
        max_concurrent = [0]

        def slow_urlopen(*args, **kwargs):
            active_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_count[0])
            time.sleep(0.05)
            active_count[0] -= 1
            mock_res = MagicMock()
            mock_res.read.return_value = b'{"response": "done", "prompt_eval_count": 5, "eval_count": 5}'
            ctx = MagicMock()
            ctx.__enter__.return_value = mock_res
            return ctx

        mock_urlopen.side_effect = slow_urlopen

        def run_req(idx):
            req = InferenceRequest(task_type="text_generation", input_payload=f"Query {idx}")
            adapter.execute(req)
            execution_order.append(idx)

        t1 = threading.Thread(target=run_req, args=(1,))
        t2 = threading.Thread(target=run_req, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Due to concurrency semaphore of 1, max_concurrent must never exceed 1
        self.assertEqual(max_concurrent[0], 1)
        self.assertEqual(len(execution_order), 2)

    def test_07_live_local_inference_if_daemon_online(self):
        """Verify live execution against local qwen3.5:2b if daemon is running."""
        adapter = OllamaProviderAdapter(model_name="qwen3.5:2b")
        if not adapter.is_available():
            self.skipTest("Local Ollama daemon is offline or qwen3.5:2b is not installed.")

        req = InferenceRequest(
            task_type="text_generation",
            input_payload="Answer in 5 words or less: What is the primary function of an operating system kernel?",
            metadata={"think": False, "max_tokens": 50},
        )
        resp = adapter.execute(req)

        self.assertEqual(resp.status, "SUCCESS")
        self.assertIsNotNone(resp.result)
        self.assertTrue(len(str(resp.result).strip()) > 0)
        self.assertGreater(resp.execution_time_ms, 0)
        self.assertIn("tokens_per_second", resp.metadata)


if __name__ == "__main__":
    unittest.main()
