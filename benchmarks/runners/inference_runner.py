"""
inference_runner.py: Real AI model inference benchmarking runner for SETU-NETRA Stage 6.

Why this file exists:
Benchmarks actual registered neural models and adapters without synthetic sleep substitutes:
1. EasyOCR (CRAFT text detection + CRNN text recognition)
2. Sentence Transformers (sentence-transformers/all-MiniLM-L6-v2, 384-dim)
3. OfflineSemanticEngine Fallback (Deterministic 512-dim feature hashing)
4. GroundedExtractiveQAAdapter (Zero-hallucination citation-grounded extractive QA)
5. LocalGenerativeAdapter (HuggingFaceTB/SmolLM2-135M-Instruct SLM)

Measures:
- Model load / warm-up cold-start latency
- First-request (cold) vs warm-request latency
- Mean, P50, P95, P99 latency
- Throughput (requests/sec and tokens/sec for generative)
- CPU utilization & Physical RAM consumption
- Token counts (prompt tokens, generated tokens)
Respects the 16 GB consumer laptop hardware ceiling by executing models sequentially.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.embedding_adapter import EmbeddingExecutionAdapter
from setu_netra.routing.adapters.generative_adapter import LocalGenerativeAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.adapters.ocr_adapter import OCRExecutionAdapter
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.semantic.embeddings.factory import get_embedding_engine

from benchmarks.experiments.experiment_tracker import ExperimentMetadata, ExperimentTracker
from benchmarks.metrics.calculator import compute_statistical_summary

logger = logging.getLogger(__name__)


class RealInferenceBenchmarkRunner:
    """Executes empirical benchmarks on genuine registered local AI models."""

    def __init__(self, tracker: Optional[ExperimentTracker] = None):
        self._tracker = tracker or ExperimentTracker()
        self._repo_root = Path(__file__).resolve().parent.parent.parent

    def benchmark_adapter(
        self,
        name: str,
        adapter_factory,
        sample_requests: List[InferenceRequest],
        warm_iterations: int = 5,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Benchmark an adapter across cold-start, warm-up, and sustained execution."""
        print(f"\n--- Benchmarking Model: {name} ---")

        # 1. Model Loading Time
        t_load_start = time.perf_counter()
        adapter = adapter_factory()
        # Trigger lazy load if applicable
        if hasattr(adapter, "load_model"):
            adapter.load_model()
        elif hasattr(adapter, "_get_engine"):
            adapter._get_engine()
        load_time_ms = (time.perf_counter() - t_load_start) * 1000.0
        print(f"  Model Loading Time: {load_time_ms:.1f} ms")

        # 2. First-Request (Cold) Latency
        first_req = sample_requests[0]
        t_cold_start = time.perf_counter()
        cold_resp = adapter.execute(first_req)
        cold_latency_ms = (time.perf_counter() - t_cold_start) * 1000.0
        print(f"  Cold-Request Latency: {cold_latency_ms:.1f} ms (Status: {cold_resp.status})")

        # 3. Warm-up Phase (1 unrecorded iteration)
        adapter.execute(first_req)

        # 4. Sustained Warm Execution
        warm_latencies: List[float] = []
        raw_traces: List[Dict[str, Any]] = []
        error_count = 0
        timeout_count = 0

        # Special metrics for generative models
        total_prompt_tokens = 0
        total_generated_tokens = 0
        total_gen_time_sec = 0.0

        t_bench_start = time.perf_counter()

        for idx in range(warm_iterations):
            req = sample_requests[(idx + 1) % len(sample_requests)]
            t_req_start = time.perf_counter()
            try:
                resp = adapter.execute(req)
                elapsed_ms = (time.perf_counter() - t_req_start) * 1000.0
                warm_latencies.append(elapsed_ms)

                trace_rec = {
                    "model": name,
                    "iteration": idx + 1,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": resp.status,
                    "error": resp.error,
                }

                if resp.status == "SUCCESS":
                    if "tokens_generated" in resp.metadata:
                        gen_toks = resp.metadata["tokens_generated"]
                        total_generated_tokens += gen_toks
                        total_gen_time_sec += elapsed_ms / 1000.0
                        trace_rec["tokens_generated"] = gen_toks
                        trace_rec["tokens_per_sec"] = resp.metadata.get("tokens_per_sec", 0.0)
                    elif "prompt_tokens" in resp.metadata:
                        total_prompt_tokens += resp.metadata["prompt_tokens"]
                elif resp.status == "TIMEOUT":
                    timeout_count += 1
                else:
                    error_count += 1

                raw_traces.append(trace_rec)

            except Exception as err:
                elapsed_ms = (time.perf_counter() - t_req_start) * 1000.0
                error_count += 1
                raw_traces.append({
                    "model": name,
                    "iteration": idx + 1,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": "FAILED",
                    "error": str(err),
                })

        total_wall_sec = time.perf_counter() - t_bench_start
        throughput_req_sec = len(warm_latencies) / max(0.001, total_wall_sec)
        sys_tel = get_system_telemetry()

        lat_stats = compute_statistical_summary(warm_latencies)
        tokens_per_sec = (total_generated_tokens / max(0.001, total_gen_time_sec)) if total_gen_time_sec > 0 else 0.0

        aggregated = {
            "model_name": name,
            "load_time_ms": round(load_time_ms, 2),
            "cold_latency_ms": round(cold_latency_ms, 2),
            "warm_iterations": warm_iterations,
            "throughput_req_sec": round(throughput_req_sec, 2),
            "latency_stats": lat_stats,
            "error_rate_percent": round((error_count / warm_iterations) * 100.0, 2),
            "timeout_rate_percent": round((timeout_count / warm_iterations) * 100.0, 2),
            "system_telemetry": {
                "cpu_percent": sys_tel.cpu_percent,
                "ram_percent": sys_tel.ram_percent,
                "avail_ram_mb": sys_tel.avail_ram_mb,
            },
        }

        if total_generated_tokens > 0:
            aggregated["generative_metrics"] = {
                "total_generated_tokens": total_generated_tokens,
                "average_tokens_per_sec": round(tokens_per_sec, 2),
                "total_generation_time_sec": round(total_gen_time_sec, 2),
            }

        print(
            f"  Warm Mean: {lat_stats['mean']:.1f}ms | P50: {lat_stats['p50']:.1f}ms | "
            f"P95: {lat_stats['p95']:.1f}ms | Throughput: {throughput_req_sec:.2f} req/s"
        )
        if total_generated_tokens > 0:
            print(f"  Generative Throughput: {tokens_per_sec:.1f} tokens/sec")

        return aggregated, raw_traces

    def execute_all_inference_benchmarks(self) -> Dict[str, Any]:
        """Sequentially evaluate all registered model adapters."""
        print("=" * 80)
        print("STAGE 6: REAL AI MODEL INFERENCE BENCHMARKS (On Local Hardware)")
        print("=" * 80)

        results: Dict[str, Any] = {}
        all_raw: List[Dict[str, Any]] = []

        # 1. EasyOCR (CRAFT + CRNN)
        img_path = str(self._repo_root / "sample_data" / "sample_question.png")
        if not os.path.exists(img_path):
            img_path = str(self._repo_root / "output" / "preprocessed_sample_question.png")
        ocr_reqs = [
            InferenceRequest(task_type="ocr", input_payload=img_path, timeout=30.0)
            for _ in range(3)
        ]
        agg_ocr, traces_ocr = self.benchmark_adapter(
            name="easyocr-craft-crnn",
            adapter_factory=lambda: OCRExecutionAdapter(model_id="easyocr-craft-crnn"),
            sample_requests=ocr_reqs,
            warm_iterations=3,
        )
        results["easyocr-craft-crnn"] = agg_ocr
        all_raw.extend(traces_ocr)

        # 2. Sentence Transformers Neural Embedding (all-MiniLM-L6-v2)
        embed_reqs = [
            InferenceRequest(
                task_type="embedding",
                input_payload=[f"Sentence {i} for dense semantic vectorization in database store."],
                timeout=10.0,
            )
            for i in range(5)
        ]
        agg_embed, traces_embed = self.benchmark_adapter(
            name="sentence-transformers/all-MiniLM-L6-v2",
            adapter_factory=lambda: EmbeddingExecutionAdapter(
                engine=get_embedding_engine("neural"),
                model_id="sentence-transformers/all-MiniLM-L6-v2",
            ),
            sample_requests=embed_reqs,
            warm_iterations=5,
        )
        results["sentence-transformers/all-MiniLM-L6-v2"] = agg_embed
        all_raw.extend(traces_embed)

        # 3. OfflineSemanticEngine (512-dim Hash Embedding Fallback)
        agg_offline, traces_offline = self.benchmark_adapter(
            name="offline-semantic-hash-512",
            adapter_factory=lambda: EmbeddingExecutionAdapter(
                engine=get_embedding_engine("offline"),
                model_id="offline-semantic-hash-512",
            ),
            sample_requests=embed_reqs,
            warm_iterations=10,
        )
        results["offline-semantic-hash-512"] = agg_offline
        all_raw.extend(traces_offline)

        # 4. GroundedExtractiveQAAdapter
        qa_reqs = [
            InferenceRequest(
                task_type="extractive_qa",
                input_payload="What is the operating frequency of the sensor?",
                context="The optical sensor operates at 144 Hz with ultra-low latency [Doc: spec.pdf, Page: 1, Block: 2].",
                metadata={"evidence_requirement": "REQUIRE_VERIFIED_CITATIONS"},
                timeout=5.0,
            )
            for _ in range(10)
        ]
        agg_qa, traces_qa = self.benchmark_adapter(
            name="grounded-extractive-qa-v1",
            adapter_factory=lambda: GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1"),
            sample_requests=qa_reqs,
            warm_iterations=10,
        )
        results["grounded-extractive-qa-v1"] = agg_qa
        all_raw.extend(traces_qa)

        # 5. LocalGenerativeAdapter (SmolLM2-135M-Instruct)
        gen_reqs = [
            InferenceRequest(
                task_type="generative_qa",
                input_payload="Explain the difference between deadlock prevention and deadlock avoidance in operating systems.",
                max_tokens=30,
                timeout=15.0,
            ),
            InferenceRequest(
                task_type="generative_qa",
                input_payload="Compare the time complexity of QuickSort vs MergeSort.",
                max_tokens=30,
                timeout=15.0,
            ),
        ]
        agg_gen, traces_gen = self.benchmark_adapter(
            name="HuggingFaceTB/SmolLM2-135M-Instruct",
            adapter_factory=lambda: LocalGenerativeAdapter(model_id="HuggingFaceTB/SmolLM2-135M-Instruct"),
            sample_requests=gen_reqs,
            warm_iterations=3,
        )
        results["HuggingFaceTB/SmolLM2-135M-Instruct"] = agg_gen
        all_raw.extend(traces_gen)

        # Persist results
        metadata = ExperimentMetadata(
            experiment_id="real_inference_benchmarks",
            suite_name="Stage 6 Real Inference Evaluation",
            description="Empirical benchmark of genuine local AI models running on consumer CPU hardware.",
            workload_id="real_models",
            total_requests=len(all_raw),
            warmup_count=1,
            repetition_count=1,
        )

        raw_path = self._tracker.save_raw_experiment_data("real_inference_benchmarks", metadata, all_raw)
        summary_path = self._tracker.save_aggregated_results("real_inference_benchmarks", metadata, results)
        print(f"\n[OK] Real model inference benchmarks completed.")
        print(f"  Raw measurements saved:    {raw_path}")
        print(f"  Aggregated results saved:  {summary_path}")

        return results
