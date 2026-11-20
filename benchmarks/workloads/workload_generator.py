"""
workload_generator.py: Standardized workload generation for scheduler microbenchmarks.

Why this file exists:
Produces deterministic, reproducible request streams across 8 distinct workload profiles:
1. Uniform short requests (5 ms)
2. Uniform long requests (40 ms)
3. Mixed short and long requests (80% short @ 5 ms, 20% long @ 40 ms)
4. Burst traffic (concurrent high-frequency arrival)
5. Queue saturation (request volume designed to exceed queue capacity and trigger backpressure)
6. Unequal worker capacity (heterogeneous worker performance topologies)
7. Worker degradation (one worker degraded with latency penalty)
8. Worker failure and recovery (transient crash injection testing circuit breaker recovery)
"""

from typing import Any, Dict, List, Tuple
from setu_netra.routing.contracts import InferenceRequest


class WorkloadGenerator:
    """Constructs reproducible request streams and worker cluster topologies."""

    @staticmethod
    def get_supported_workload_profiles() -> List[str]:
        return [
            "uniform_short",
            "uniform_long",
            "mixed_sizes",
            "burst",
            "queue_saturation",
            "unequal_worker_capacity",
            "worker_degradation",
            "worker_failure_and_recovery",
        ]

    @staticmethod
    def generate_requests(
        profile: str,
        count: int = 30,
        warmup: bool = False,
    ) -> List[InferenceRequest]:
        """Generate a reproducible sequence of InferenceRequest instances."""
        requests: List[InferenceRequest] = []
        prefix = "warmup" if warmup else "eval"

        for i in range(count):
            if profile == "uniform_short":
                target_lat = 5.0
                payload = f"Short task payload {i}"
            elif profile == "uniform_long":
                target_lat = 40.0
                payload = f"Long execution payload {i} " * 10
            elif profile == "mixed_sizes":
                # 80% short (5ms), 20% long (40ms)
                is_long = (i % 5 == 0)
                target_lat = 40.0 if is_long else 5.0
                payload = f"{'Long' if is_long else 'Short'} payload {i}"
            elif profile == "burst":
                target_lat = 8.0
                payload = f"Burst request payload {i}"
            elif profile == "queue_saturation":
                target_lat = 25.0
                payload = f"Queue fill payload {i}"
            elif profile == "unequal_worker_capacity":
                target_lat = 10.0
                payload = f"Heterogeneous cluster payload {i}"
            elif profile == "worker_degradation":
                target_lat = 8.0
                payload = f"Degradation test payload {i}"
            elif profile == "worker_failure_and_recovery":
                target_lat = 8.0
                payload = f"Fault injection test payload {i}"
            else:
                target_lat = 10.0
                payload = f"Standard request payload {i}"

            req = InferenceRequest(
                task_type="benchmark",
                input_payload=f"[{prefix}] {payload}",
                timeout=15.0,
                metadata={
                    "target_latency_ms": target_lat,
                    "profile": profile,
                    "seq_index": i,
                    "is_warmup": warmup,
                },
            )
            requests.append(req)

        return requests

    @staticmethod
    def get_worker_topology_for_workload(profile: str) -> List[Dict[str, Any]]:
        """Return worker configurations for a specific workload profile."""
        if profile == "unequal_worker_capacity":
            # Worker 1 is fast (5ms), Worker 2 is medium (15ms), Worker 3 is slow (35ms)
            return [
                {"worker_id": "w_fast", "latency_ms": 5.0, "queue_size": 50},
                {"worker_id": "w_med", "latency_ms": 15.0, "queue_size": 50},
                {"worker_id": "w_slow", "latency_ms": 35.0, "queue_size": 50},
            ]
        elif profile == "worker_degradation":
            # Worker 2 is marked degraded
            return [
                {"worker_id": "w_healthy_1", "latency_ms": 8.0, "queue_size": 50},
                {"worker_id": "w_degraded", "latency_ms": 8.0, "degraded": True, "queue_size": 50},
                {"worker_id": "w_healthy_2", "latency_ms": 8.0, "queue_size": 50},
            ]
        elif profile == "worker_failure_and_recovery":
            # Worker 1 experiences 30% transient failures
            return [
                {"worker_id": "w_unstable", "latency_ms": 8.0, "failure_rate": 0.30, "queue_size": 50},
                {"worker_id": "w_stable_1", "latency_ms": 8.0, "queue_size": 50},
                {"worker_id": "w_stable_2", "latency_ms": 8.0, "queue_size": 50},
            ]
        elif profile == "queue_saturation":
            # Small queue capacity (max_queue_size=3) to reliably test backpressure
            return [
                {"worker_id": "w_small_1", "latency_ms": 25.0, "queue_size": 3},
                {"worker_id": "w_small_2", "latency_ms": 25.0, "queue_size": 3},
            ]
        else:
            # Standard homogeneous 3-worker cluster
            return [
                {"worker_id": "w1", "latency_ms": 8.0, "queue_size": 50},
                {"worker_id": "w2", "latency_ms": 8.0, "queue_size": 50},
                {"worker_id": "w3", "latency_ms": 8.0, "queue_size": 50},
            ]
