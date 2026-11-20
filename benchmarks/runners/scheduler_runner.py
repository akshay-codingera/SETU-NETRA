"""
scheduler_runner.py: Systematic microbenchmarking runner for the 6 traffic schedulers.

Why this file exists:
Executes rigorous, reproducible evaluations of:
1. Round Robin
2. Random
3. Least Outstanding Requests (LOR)
4. Shortest Estimated Completion Time (SECT)
5. Capacity-Aware Scheduling (CAS)
6. Adaptive Resilient Scheduling (ARS)
across 8 standardized workload profiles with separate warm-up phases and independent repetitions.
Persists raw per-request traces and aggregated percentiles.
"""

import concurrent.futures
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelCategory,
    ModelMetadata,
    WorkerState,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.schedulers import (
    AdaptiveResilientScheduler,
    BaseScheduler,
    CapacityAwareScheduler,
    LeastOutstandingRequestsScheduler,
    RandomScheduler,
    RoundRobinScheduler,
    ShortestEstimatedCompletionTimeScheduler,
)
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool

from benchmarks.experiments.experiment_tracker import ExperimentMetadata, ExperimentTracker
from benchmarks.metrics.calculator import compute_statistical_summary
from benchmarks.workloads.workload_generator import WorkloadGenerator

logger = logging.getLogger(__name__)


class SyntheticBenchmarkAdapter(BaseModelAdapter):
    """Calibrated adapter with synthetic execution duration and fault injection."""

    def __init__(
        self,
        worker_id: str,
        base_latency_ms: float = 10.0,
        failure_rate: float = 0.0,
    ):
        self._worker_id = worker_id
        self._model_id = "synthetic-benchmark-model"
        self._base_latency_ms = base_latency_ms
        self._failure_rate = failure_rate
        self._is_healthy = True
        self._rng = random.Random(42 + hash(worker_id) % 1000)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return ["benchmark"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name="Synthetic Benchmark Model",
            model_type=ModelCategory.EXTRACTIVE_QA,
            supported_tasks=self.task_types,
            provider="Benchmark Harness",
            execution_backend="SYNTHETIC_WORKLOAD",
            memory_requirement={"min_ram_mb": 20},
            context_length=2048,
            worker_id=self._worker_id,
        )

    def is_available(self) -> bool:
        return self._is_healthy

    def health_check(self) -> bool:
        return self._is_healthy

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        exec_ms = request.metadata.get("target_latency_ms", self._base_latency_ms)
        if exec_ms > 0:
            time.sleep(exec_ms / 1000.0)

        if self._failure_rate > 0.0 and self._rng.random() < self._failure_rate:
            raise RuntimeError(f"Synthetic transient failure on {self._worker_id}")

        return InferenceResponse(
            request_id=request.request_id,
            result="synthetic_success",
            model_id=self._model_id,
            execution_time_ms=round(exec_ms, 2),
            status="SUCCESS",
            metadata={"worker_id": self._worker_id},
        )


class SchedulerBenchmarkRunner:
    """Executes the complete matrix of 6 schedulers x 8 workloads."""

    def __init__(self, tracker: Optional[ExperimentTracker] = None):
        self._tracker = tracker or ExperimentTracker()

    def _setup_workers(
        self,
        pool: InferenceWorkerPool,
        configs: List[Dict[str, Any]],
    ) -> List[InferenceWorker]:
        workers: List[InferenceWorker] = []
        for cfg in configs:
            adapter = SyntheticBenchmarkAdapter(
                worker_id=cfg["worker_id"],
                base_latency_ms=cfg.get("latency_ms", 10.0),
                failure_rate=cfg.get("failure_rate", 0.0),
            )
            worker = pool.create_worker(
                adapter=adapter,
                worker_id=cfg["worker_id"],
                max_queue_size=cfg.get("queue_size", 50),
            )
            if cfg.get("degraded", False):
                worker._state = WorkerState.DEGRADED
            workers.append(worker)
        return workers

    def run_single_scheduler_evaluation(
        self,
        scheduler: BaseScheduler,
        profile: str,
        repetition_count: int = 3,
        requests_per_rep: int = 30,
        warmup_count: int = 5,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Run warm-up followed by multiple repetitions for a single scheduler and workload."""
        configs = WorkloadGenerator.get_worker_topology_for_workload(profile)
        is_concurrent = (profile in ("burst", "queue_saturation"))

        # 1. Warm-up Phase (Unrecorded)
        if warmup_count > 0:
            warmup_pool = InferenceWorkerPool()
            warmup_workers = self._setup_workers(warmup_pool, configs)
            warmup_reqs = WorkloadGenerator.generate_requests(profile, count=warmup_count, warmup=True)
            for req in warmup_reqs:
                try:
                    if isinstance(scheduler, AdaptiveResilientScheduler):
                        scheduler.execute_with_resilience(req, warmup_workers)
                    else:
                        cand = [w for w in warmup_workers if w.is_available()]
                        sel = scheduler.select_worker(req, cand)
                        if sel:
                            fut = sel.submit(req)
                            fut.result(timeout=req.timeout)
                except Exception:
                    pass
            warmup_pool.stop_all(drain=False, timeout=1.0)

        # 2. Evaluation Repetitions
        all_raw_traces: List[Dict[str, Any]] = []
        rep_throughputs: List[float] = []
        rep_latencies: List[float] = []
        rep_queue_waits: List[float] = []
        rep_overheads: List[float] = []

        total_submitted = 0
        total_completed = 0
        total_rejected = 0
        total_failed = 0
        total_timeouts = 0

        for rep_idx in range(repetition_count):
            pool = InferenceWorkerPool()
            workers = self._setup_workers(pool, configs)
            reqs = WorkloadGenerator.generate_requests(profile, count=requests_per_rep, warmup=False)
            total_submitted += len(reqs)

            t_start = time.perf_counter()

            def dispatch_task(request: InferenceRequest) -> Tuple[InferenceResponse, float]:
                t0 = time.perf_counter()
                if isinstance(scheduler, AdaptiveResilientScheduler):
                    t_sched_us = (time.perf_counter() - t0) * 1e6
                    resp = scheduler.execute_with_resilience(request, workers)
                    return resp, t_sched_us
                else:
                    cand = [w for w in workers if w.is_available()]
                    selected = scheduler.select_worker(request, cand)
                    t_sched_us = (time.perf_counter() - t0) * 1e6
                    if selected is None:
                        return InferenceResponse(
                            request_id=request.request_id,
                            result=None,
                            model_id="benchmark",
                            status="REJECTED",
                            error="Backpressure: No eligible worker available.",
                        ), t_sched_us

                    try:
                        fut = selected.submit(request)
                        resp = fut.result(timeout=request.timeout + 1.0)
                        return resp, t_sched_us
                    except Exception as err:
                        return InferenceResponse(
                            request_id=request.request_id,
                            result=None,
                            model_id="benchmark",
                            status="FAILED",
                            error=str(err),
                        ), t_sched_us

            if is_concurrent:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(reqs), 16)) as executor:
                    futures = [executor.submit(dispatch_task, r) for r in reqs]
                    for fut in concurrent.futures.as_completed(futures):
                        try:
                            resp, t_sched_us = fut.result()
                            raw_rec = {
                                "repetition": rep_idx + 1,
                                "request_id": resp.request_id,
                                "status": resp.status,
                                "latency_ms": resp.execution_time_ms,
                                "queue_wait_ms": resp.metadata.get("queue_wait_ms", 0.0),
                                "overhead_us": round(t_sched_us, 2),
                                "worker_id": resp.metadata.get("worker_id"),
                                "error": resp.error,
                            }
                            all_raw_traces.append(raw_rec)
                            rep_overheads.append(t_sched_us)

                            if resp.status == "SUCCESS":
                                total_completed += 1
                                rep_latencies.append(resp.execution_time_ms)
                                rep_queue_waits.append(resp.metadata.get("queue_wait_ms", 0.0))
                            elif resp.status == "REJECTED":
                                total_rejected += 1
                            elif resp.status == "TIMEOUT":
                                total_timeouts += 1
                            else:
                                total_failed += 1
                        except Exception:
                            total_failed += 1
            else:
                for r in reqs:
                    try:
                        resp, t_sched_us = dispatch_task(r)
                        raw_rec = {
                            "repetition": rep_idx + 1,
                            "request_id": resp.request_id,
                            "status": resp.status,
                            "latency_ms": resp.execution_time_ms,
                            "queue_wait_ms": resp.metadata.get("queue_wait_ms", 0.0),
                            "overhead_us": round(t_sched_us, 2),
                            "worker_id": resp.metadata.get("worker_id"),
                            "error": resp.error,
                        }
                        all_raw_traces.append(raw_rec)
                        rep_overheads.append(t_sched_us)

                        if resp.status == "SUCCESS":
                            total_completed += 1
                            rep_latencies.append(resp.execution_time_ms)
                            rep_queue_waits.append(resp.metadata.get("queue_wait_ms", 0.0))
                        elif resp.status == "REJECTED":
                            total_rejected += 1
                        elif resp.status == "TIMEOUT":
                            total_timeouts += 1
                        else:
                            total_failed += 1
                    except Exception:
                        total_failed += 1

            t_wall = time.perf_counter() - t_start
            rep_thr = len(reqs) / max(0.001, t_wall)
            rep_throughputs.append(rep_thr)
            pool.stop_all(drain=False, timeout=1.0)

        # 3. Aggregate metrics across repetitions
        sys_tel = get_system_telemetry()
        aggregated = {
            "scheduler": scheduler.name,
            "workload_profile": profile,
            "repetitions": repetition_count,
            "requests_submitted": total_submitted,
            "requests_completed": total_completed,
            "requests_rejected": total_rejected,
            "requests_failed": total_failed,
            "requests_timed_out": total_timeouts,
            "success_rate_percent": round((total_completed / total_submitted) * 100.0, 2) if total_submitted else 0.0,
            "throughput_req_sec": compute_statistical_summary(rep_throughputs),
            "latency_ms": compute_statistical_summary(rep_latencies),
            "queue_wait_ms": compute_statistical_summary(rep_queue_waits),
            "scheduling_overhead_us": compute_statistical_summary(rep_overheads),
            "system_telemetry": {
                "cpu_percent": sys_tel.cpu_percent,
                "ram_percent": sys_tel.ram_percent,
                "avail_ram_mb": sys_tel.avail_ram_mb,
            },
        }

        return aggregated, all_raw_traces

    def execute_full_suite(
        self,
        repetition_count: int = 3,
        requests_per_rep: int = 25,
    ) -> Dict[str, Any]:
        """Execute all 6 schedulers across all 8 workloads."""
        schedulers: List[BaseScheduler] = [
            RoundRobinScheduler(),
            RandomScheduler(seed=42),
            LeastOutstandingRequestsScheduler(),
            ShortestEstimatedCompletionTimeScheduler(),
            CapacityAwareScheduler(),
            AdaptiveResilientScheduler(inner_scheduler=CapacityAwareScheduler()),
        ]

        workload_profiles = WorkloadGenerator.get_supported_workload_profiles()
        full_results: Dict[str, Dict[str, Any]] = {}
        all_raw_data: List[Dict[str, Any]] = []

        print("=" * 80)
        print("STAGE 6: SCHEDULER MICROBENCHMARKS (6 Schedulers x 8 Workloads)")
        print(f"Repetitions: {repetition_count} | Requests per Repetition: {requests_per_rep}")
        print("=" * 80)

        for profile in workload_profiles:
            print(f"\n>>> Running Workload: {profile.upper()} <<<")
            full_results[profile] = {}

            for sched in schedulers:
                agg, traces = self.run_single_scheduler_evaluation(
                    scheduler=sched,
                    profile=profile,
                    repetition_count=repetition_count,
                    requests_per_rep=requests_per_rep,
                    warmup_count=5,
                )
                full_results[profile][sched.name] = agg
                for t in traces:
                    t["scheduler"] = sched.name
                    t["profile"] = profile
                all_raw_data.extend(traces)

                th_mean = agg["throughput_req_sec"]["mean"]
                lat_p95 = agg["latency_ms"]["p95"]
                wait_mean = agg["queue_wait_ms"]["mean"]
                succ_pct = agg["success_rate_percent"]
                print(
                    f"  [{sched.name:22s}] Throughput: {th_mean:6.1f} req/s | "
                    f"P95: {lat_p95:5.1f}ms | Wait: {wait_mean:4.1f}ms | "
                    f"Success: {succ_pct:5.1f}%"
                )

        # Persist results
        metadata = ExperimentMetadata(
            experiment_id="scheduler_microbenchmarks",
            suite_name="Stage 6 Scheduler Evaluation",
            description="Comparative microbenchmark of 6 schedulers across 8 workload profiles.",
            workload_id="all_8_workloads",
            total_requests=len(all_raw_data),
            warmup_count=5,
            repetition_count=repetition_count,
        )

        raw_path = self._tracker.save_raw_experiment_data("scheduler_microbenchmarks", metadata, all_raw_data)
        summary_path = self._tracker.save_aggregated_results("scheduler_microbenchmarks", metadata, full_results)
        print(f"\n[OK] Scheduler benchmark completed.")
        print(f"  Raw measurements saved:    {raw_path}")
        print(f"  Aggregated results saved:  {summary_path}")

        return full_results
