"""
demonstrate_stage5.py: Authoritative Stage 5 Live Demonstration.

Demonstrates:
1. Multiple incoming requests across different task types.
2. Task-aware and intent-aware model routing (AdaptiveModelRouter).
3. Dispatch to multiple worker instances per model.
4. Comparison of scheduling strategies (Round Robin, Least Outstanding, Capacity-Aware, Resilient).
5. Worker overload and backpressure enforcement.
6. Worker failure detection, circuit breaking, and automatic retry recovery.
7. Actual measured wall-clock latencies, throughput, and host CPU/RAM telemetry.
"""

import sys
import time
from pathlib import Path

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.contracts import EvidenceRequirement, InferenceRequest
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import ModelRegistry
from setu_netra.routing.schedulers import (
    AdaptiveResilientScheduler,
    CapacityAwareScheduler,
    LeastOutstandingRequestsScheduler,
    RoundRobinScheduler,
)
from setu_netra.routing.worker_pool import InferenceWorkerPool


def run_stage5_demonstration():
    print("=" * 80)
    print("SETU-NETRA STAGE 5: ADAPTIVE MODEL ROUTING & TRAFFIC MANAGEMENT DEMO")
    print("=" * 80)

    # 1. Setup Architecture
    registry = ModelRegistry(register_defaults=True)
    worker_pool = InferenceWorkerPool()

    # Create multi-worker pool for Grounded Extractive QA (2 worker replicas)
    qa_adapter_1 = GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1", worker_id="qa_worker_alpha")
    qa_adapter_2 = GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1", worker_id="qa_worker_beta")
    w_qa_1 = worker_pool.create_worker(qa_adapter_1, worker_id="qa_worker_alpha", max_queue_size=5)
    w_qa_2 = worker_pool.create_worker(qa_adapter_2, worker_id="qa_worker_beta", max_queue_size=5)

    pipeline = IntelligentInferencePipeline(
        registry=registry,
        worker_pool=worker_pool,
        auto_spawn_workers=True,  # Spawns default workers for classifier, embeddings, etc.
    )

    print(f"\n[1] Control Plane & Worker Pool Initialized:")
    print(f"  * Multi-worker replicas for Extractive QA: {w_qa_1.worker_id}, {w_qa_2.worker_id}")
    print(f"  * Active Workers in Pool: {len(worker_pool.get_all_workers())}")

    # 2. Task-Aware & Intent-Aware Model Selection
    print("\n" + "-" * 80)
    print("[2] Task-Aware & Intent-Aware Model Selection via AdaptiveModelRouter")
    print("-" * 80)
    test_queries = [
        ("qa", "What is the operating frequency of the sensor?", "Factual query with verified evidence requirements"),
        ("qa", "Compare the asymptotic complexity of QuickSort vs MergeSort.", "Comparative synthesis intent"),
        ("classification", "Orthogonal matrices and singular value decomposition in Hilbert spaces.", "Academic domain categorization"),
    ]

    for task, q, desc in test_queries:
        req = InferenceRequest(
            task_type=task,
            input_payload=q,
            context="The optical sensor operates at 144 Hz with ultra-low latency [Doc: spec.pdf, Page: 1, Block: 2]." if "sensor" in q else None,
            metadata={"evidence_requirement": EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS if "sensor" in q else None},
        )
        decision = pipeline.router.route(req)
        print(f"Query:        '{q}'")
        print(f"Scenario:     {desc}")
        print(f"Decision:     Selected Model -> [{decision.selected_model_id}] (Status: {decision.status})")
        print(f"Confidence:   {decision.confidence * 100:.0f}% | Reason: {decision.reason}\n")

    # 3. Multi-Worker Dispatch across Schedulers
    print("-" * 80)
    print("[3] Multi-Worker Load Distribution (Round-Robin vs Least-Outstanding)")
    print("-" * 80)
    sample_req = InferenceRequest(
        task_type="extractive_qa",
        model_id="grounded-extractive-qa-v1",
        input_payload="What is the operating frequency?",
        context="The optical sensor operates at 144 Hz [Doc: spec.pdf, Page: 1, Block: 2].",
    )

    # Test Round-Robin distribution
    pipeline.set_scheduler(RoundRobinScheduler())
    res_rr_1 = pipeline.execute(sample_req)
    res_rr_2 = pipeline.execute(sample_req)
    w_rr_1 = res_rr_1.metadata.get("worker_id")
    w_rr_2 = res_rr_2.metadata.get("worker_id")
    print(f"RoundRobin: Request 1 routed to -> {w_rr_1} | Request 2 routed to -> {w_rr_2}")

    # Test Least Outstanding Requests
    pipeline.set_scheduler(LeastOutstandingRequestsScheduler())
    res_lor = pipeline.execute(sample_req)
    print(f"LeastOutstanding: Request routed to -> {res_lor.metadata.get('worker_id')} (Execution Latency: {res_lor.execution_time_ms} ms)")

    # 4. Worker Overload & Backpressure Enforcement
    print("\n" + "-" * 80)
    print("[4] Worker Overload & Backpressure Verification")
    print("-" * 80)
    print("Testing queue limit backpressure (Max queue size = 5)...")
    # Temporarily fill w_qa_1's queue
    held_futures = []
    try:
        # Fill queue to maximum capacity
        for i in range(10):
            held_futures.append(w_qa_1.submit(InferenceRequest(task_type="qa", input_payload=f"heavy_{i}", timeout=1.0)))
    except Exception as e:
        print(f"Backpressure Signal Triggered as Expected: {e}")

    # 5. Worker Failure & Resilient Recovery
    print("\n" + "-" * 80)
    print("[5] Resilient Self-Healing & Failure Recovery")
    print("-" * 80)
    resilient_sched = AdaptiveResilientScheduler(inner_scheduler=CapacityAwareScheduler(), max_retries=2)
    pipeline.set_scheduler(resilient_sched)

    # Trigger temporary cooldown on alpha worker to simulate unexpected failure
    w_qa_1.trigger_cooldown(duration_sec=3.0)
    print(f"Worker '{w_qa_1.worker_id}' placed into temporary COOLING_DOWN state (simulated outage).")
    print(f"Worker '{w_qa_1.worker_id}' is available: {w_qa_1.is_available()}")

    # Dispatch request: Resilient scheduler must transparently route to w_qa_2!
    failover_res = pipeline.execute(sample_req)
    print(f"Failover Dispatch: Status -> {failover_res.status} | Servicing Worker -> {failover_res.metadata.get('worker_id')}")
    print(f"Grounded Result:   {failover_res.result}")
    print(f"Epistemic Status:  {failover_res.metadata.get('epistemic_status')}")

    # 6. Actual Latency & Telemetry Metrics
    print("\n" + "-" * 80)
    print("[6] Live Hardware Resource Telemetry & Execution Summary")
    print("-" * 80)
    pipe_tel = failover_res.metadata.get("pipeline_telemetry", {})
    sys_tel = pipe_tel.get("system_telemetry", {})
    print(f"End-to-End Pipeline Latency: {pipe_tel.get('total_latency_ms')} ms")
    print(f"Host Hardware CPU Usage:     {sys_tel.get('cpu_percent')}%")
    print(f"Host Hardware RAM Load:      {sys_tel.get('ram_percent')}% (Available: {sys_tel.get('avail_ram_mb')} MB)")

    pipeline.shutdown(drain=False, timeout=1.0)
    print("\n" + "=" * 80)
    print("STAGE 5 COMPLETE: ADAPTIVE ROUTING & TRAFFIC MANAGEMENT OPERATIONAL")
    print("=" * 80)


if __name__ == "__main__":
    run_stage5_demonstration()
