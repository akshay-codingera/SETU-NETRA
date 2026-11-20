"""
load_generator.py: Multi-threaded Poisson traffic load generator for SETU-NETRA V1.1.
Executes controlled arrival-rate benchmarks against worker pools to measure:
- Queue wait time
- Execution latency
- Total latency
- Goodput & Throughput
- Tail percentiles (P50, P95, P99) with sufficient sample size (N >= 1,000)
- Circuit-breaker states and rejection rates under saturation
"""

import concurrent.futures
import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from setu_netra.routing.contracts import InferenceRequest, InferenceResponse
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.schedulers.round_robin import RoundRobinScheduler
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool

logger = logging.getLogger(__name__)


class CalibratedMockAdapter(BaseModelAdapter):
    """Adapter with calibrated empirical execution delays matching real models."""

    def __init__(self, model_id: str, mean_ms: float, std_ms: float, task_type: str = "qa"):
        self._model_id = model_id
        self._mean_ms = mean_ms
        self._std_ms = std_ms
        self._task_type = task_type
        self._available = True

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def task_type(self) -> str:
        return self._task_type

    @property
    def task_types(self) -> List[str]:
        return [self._task_type]

    def is_available(self) -> bool:
        return self._available

    def set_available(self, status: bool) -> None:
        self._available = status

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        start_t = time.perf_counter()
        # Sample log-normal execution time centered on mean_ms
        sim_delay = max(0.001, np.random.normal(self._mean_ms / 1000.0, self._std_ms / 1000.0))
        time.sleep(sim_delay)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return InferenceResponse(
            request_id=request.request_id,
            result=f"Completed by {self._model_id}",
            model_id=self._model_id,
            execution_time_ms=round(elapsed_ms, 2),
            status="SUCCESS",
        )


def run_scheduler_load_benchmark(
    condition_name: str,
    scheduler: BaseScheduler,
    total_requests: int = 1000,
    arrival_rate_lambda: float = 25.0,
    num_client_threads: int = 8,
    is_adaptive_routing: bool = False,
    random_seed: int = 42,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Runs a controlled load test with N >= 1,000 requests to measure queueing and P99 latency.

    Args:
        condition_name: Tag for this experiment (e.g. 'Condition_A', 'Condition_B', etc.)
        scheduler: Active BaseScheduler instance
        total_requests: Number of requests to issue (default 1,000 for valid P99 estimation)
        arrival_rate_lambda: Target Poisson arrival rate (requests per second)
        num_client_threads: Concurrent client generator threads
        is_adaptive_routing: If True, distributes requests between fast extractive and SLM
        random_seed: Deterministic random seed

    Returns:
        (raw_request_records, summary_statistics)
    """
    np.random.seed(random_seed)
    random.seed(random_seed)

    # Setup isolated worker pool
    pool = InferenceWorkerPool()

    # Adapters
    # Generative SLM: mean=120ms (simulated lightweight representation of SLM CPU execution under load), std=25ms
    slm_adapter = CalibratedMockAdapter("smollm2-135m-instruct", mean_ms=120.0, std_ms=25.0, task_type="qa")
    # Extractive QA: mean=1.5ms, std=0.5ms
    ext_adapter = CalibratedMockAdapter("grounded-extractive-qa-v1", mean_ms=1.5, std_ms=0.5, task_type="extractive_qa")

    # Create 3 workers per model
    slm_workers = [
        pool.create_worker(slm_adapter, worker_id=f"slm_worker_{i+1}", max_queue_size=10)
        for i in range(3)
    ]
    ext_workers = [
        pool.create_worker(ext_adapter, worker_id=f"ext_worker_{i+1}", max_queue_size=10)
        for i in range(3)
    ]

    all_workers = slm_workers + ext_workers

    # Generate Poisson arrival intervals: interval = -ln(U) / lambda
    intervals = np.random.exponential(scale=1.0 / arrival_rate_lambda, size=total_requests)

    raw_records: List[Dict[str, Any]] = []
    start_bench_time = time.perf_counter()

    # We submit requests following the Poisson schedule
    def execute_single_request(req_idx: int) -> Dict[str, Any]:
        req_start_time = time.perf_counter()
        corr_id = f"LOAD_{condition_name}_{req_idx:05d}_{uuid.uuid4().hex[:6]}"

        # Model routing decision
        if is_adaptive_routing:
            # 70% factual queries routed to extractive, 30% comparative/synthesis routed to SLM
            is_extractive = (req_idx % 10) < 7
            target_model = "grounded-extractive-qa-v1" if is_extractive else "smollm2-135m-instruct"
            target_task = "extractive_qa" if is_extractive else "qa"
            candidate_workers = ext_workers if is_extractive else slm_workers
        else:
            # Fixed Model: All requests routed to SLM
            target_model = "smollm2-135m-instruct"
            target_task = "qa"
            candidate_workers = slm_workers

        req = InferenceRequest(
            request_id=corr_id,
            task_type=target_task,
            model_id=target_model,
            prompt_or_payload=f"Benchmark query {req_idx}",
            timeout_ms=3000.0,
        )

        # Worker Scheduling
        sched_decision = scheduler.schedule(req, candidate_workers)
        if sched_decision.status == "REJECTED" or not sched_decision.selected_worker_id:
            elapsed_ms = (time.perf_counter() - req_start_time) * 1000.0
            return {
                "request_id": corr_id,
                "query_index": req_idx,
                "condition": condition_name,
                "routing_policy": "adaptive" if is_adaptive_routing else "fixed_slm",
                "selected_model": target_model,
                "selected_worker": "none",
                "queue_wait_ms": 0.0,
                "execution_time_ms": 0.0,
                "total_latency_ms": round(elapsed_ms, 2),
                "status": "REJECTED",
                "reason": sched_decision.reason,
            }

        worker = pool.get_worker(sched_decision.selected_worker_id)
        if worker is None:
            elapsed_ms = (time.perf_counter() - req_start_time) * 1000.0
            return {
                "request_id": corr_id,
                "query_index": req_idx,
                "condition": condition_name,
                "routing_policy": "adaptive" if is_adaptive_routing else "fixed_slm",
                "selected_model": target_model,
                "selected_worker": sched_decision.selected_worker_id,
                "queue_wait_ms": 0.0,
                "execution_time_ms": 0.0,
                "total_latency_ms": round(elapsed_ms, 2),
                "status": "FAILED",
                "reason": "Worker not found in pool",
            }

        queue_submit_t = time.perf_counter()
        try:
            future = worker.submit(req)
            resp = future.result(timeout=4.0)
            now_t = time.perf_counter()
            total_lat_ms = (now_t - req_start_time) * 1000.0
            exec_ms = resp.execution_time_ms
            queue_wait_ms = max(0.0, total_lat_ms - exec_ms)

            return {
                "request_id": corr_id,
                "query_index": req_idx,
                "condition": condition_name,
                "routing_policy": "adaptive" if is_adaptive_routing else "fixed_slm",
                "selected_model": target_model,
                "selected_worker": worker.worker_id,
                "queue_wait_ms": round(queue_wait_ms, 2),
                "execution_time_ms": round(exec_ms, 2),
                "total_latency_ms": round(total_lat_ms, 2),
                "status": resp.status,
                "reason": "Completed",
            }
        except Exception as err:
            elapsed_ms = (time.perf_counter() - req_start_time) * 1000.0
            return {
                "request_id": corr_id,
                "query_index": req_idx,
                "condition": condition_name,
                "routing_policy": "adaptive" if is_adaptive_routing else "fixed_slm",
                "selected_model": target_model,
                "selected_worker": worker.worker_id,
                "queue_wait_ms": 0.0,
                "execution_time_ms": 0.0,
                "total_latency_ms": round(elapsed_ms, 2),
                "status": "TIMEOUT",
                "reason": str(err),
            }

    # Execute workload with thread pool
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_client_threads)
    futures = []

    for i in range(total_requests):
        fut = executor.submit(execute_single_request, i)
        futures.append(fut)
        # Sleep Poisson inter-arrival delta
        if i < total_requests - 1:
            time.sleep(intervals[i])

    # Collect all results
    for fut in concurrent.futures.as_completed(futures):
        rec = fut.result()
        raw_records.append(rec)

    total_bench_duration = time.perf_counter() - start_bench_time

    # Cleanup workers
    pool.stop_all(drain=True, timeout=3.0)
    executor.shutdown(wait=True)

    # Sort records by query_index
    raw_records.sort(key=lambda r: r["query_index"])

    # Aggregate metrics
    latencies = [r["total_latency_ms"] for r in raw_records if r["status"] == "SUCCESS"]
    wait_times = [r["queue_wait_ms"] for r in raw_records if r["status"] == "SUCCESS"]
    exec_times = [r["execution_time_ms"] for r in raw_records if r["status"] == "SUCCESS"]

    success_count = sum(1 for r in raw_records if r["status"] == "SUCCESS")
    rejection_count = sum(1 for r in raw_records if r["status"] == "REJECTED")
    timeout_count = sum(1 for r in raw_records if r["status"] in ("TIMEOUT", "FAILED"))

    # SLO: Latency <= 500ms
    slo_violations = sum(1 for r in raw_records if r["status"] == "SUCCESS" and r["total_latency_ms"] > 500.0)

    from benchmarks.v1_1.harness.metrics import compute_percentiles_with_ci

    pct_latency = compute_percentiles_with_ci(latencies, percentiles=(50.0, 95.0, 99.0))
    pct_wait = compute_percentiles_with_ci(wait_times, percentiles=(50.0, 95.0, 99.0))

    throughput = total_requests / total_bench_duration if total_bench_duration > 0 else 0.0
    goodput = success_count / total_bench_duration if total_bench_duration > 0 else 0.0

    summary = {
        "condition": condition_name,
        "total_requests": total_requests,
        "target_arrival_rate_lambda": arrival_rate_lambda,
        "total_bench_duration_sec": round(total_bench_duration, 2),
        "success_count": success_count,
        "rejection_count": rejection_count,
        "timeout_count": timeout_count,
        "rejection_rate": round(rejection_count / total_requests, 4),
        "failure_rate": round((rejection_count + timeout_count) / total_requests, 4),
        "slo_violations": slo_violations,
        "slo_violation_rate": round(slo_violations / max(1, success_count), 4),
        "throughput_req_per_sec": round(throughput, 2),
        "goodput_req_per_sec": round(goodput, 2),
        "latency_percentiles_ms": pct_latency,
        "queue_wait_percentiles_ms": pct_wait,
        "mean_latency_ms": round(float(np.mean(latencies)), 2) if latencies else 0.0,
        "mean_queue_wait_ms": round(float(np.mean(wait_times)), 2) if wait_times else 0.0,
        "mean_execution_ms": round(float(np.mean(exec_times)), 2) if exec_times else 0.0,
    }

    return raw_records, summary
