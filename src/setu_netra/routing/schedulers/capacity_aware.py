"""
capacity_aware.py: Multidimensional capacity-aware traffic scheduler for SETU-NETRA.

Why this file exists:
Schedules inference traffic by normalizing and evaluating real-time system resource
utilization (CPU%, available RAM), worker queue backlogs, active execution concurrency,
historical EWMA latency, and operational health.
Avoids unnormalized sums; strictly normalizes each factor to [0, 1].
"""

from typing import List, Optional

from setu_netra.routing.contracts import InferenceRequest, WorkerState
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.system_telemetry import get_system_telemetry
from setu_netra.routing.worker_pool import InferenceWorker


class CapacityAwareScheduler(BaseScheduler):
    """Capacity-aware scheduler balancing queue depth, latency, and host system pressure."""

    def __init__(
        self,
        weight_load: float = 0.50,
        weight_latency: float = 0.30,
        weight_system: float = 0.20,
        cpu_threshold_pct: float = 85.0,
        ram_threshold_pct: float = 90.0,
    ):
        # Normalize weights so sum equals 1.0
        total_w = weight_load + weight_latency + weight_system
        self._w_load = weight_load / total_w
        self._w_latency = weight_latency / total_w
        self._w_system = weight_system / total_w

        self._cpu_threshold = cpu_threshold_pct
        self._ram_threshold = ram_threshold_pct

    @property
    def name(self) -> str:
        return "CAPACITY_AWARE"

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None

        # 1. Fetch genuine system resource telemetry
        sys_tel = get_system_telemetry()
        has_valid_telemetry = (
            sys_tel is not None
            and getattr(sys_tel, "is_valid", True)
            and getattr(sys_tel, "is_real", True)
            and not (hasattr(sys_tel, "is_stale") and sys_tel.is_stale(max_age_sec=5.0))
        )

        # 2. Extract model memory requirement & check host RAM adequacy if telemetry is valid
        if has_valid_telemetry:
            min_ram_req_mb = 50.0
            sample_meta = candidates[0].adapter.metadata
            if sample_meta and sample_meta.memory_requirement:
                min_ram_req_mb = float(sample_meta.memory_requirement.get("min_ram_mb", 50.0))
            if sys_tel.avail_ram_mb < min_ram_req_mb:
                # Insufficient host RAM for model execution
                return None

        # 3. Filter eligible workers (not saturated, queue not full)
        eligible: List[InferenceWorker] = []
        for w in candidates:
            if not w.is_available():
                continue
            total_backlog = w.active_requests + w.queued_requests
            if total_backlog >= w.max_queue_size:
                continue  # Saturated, backpressure
            eligible.append(w)

        if not eligible:
            return None

        # 4. Compute system pressure penalty R_sys in [0, 1]
        if has_valid_telemetry:
            cpu_excess = max(0.0, (sys_tel.cpu_percent - self._cpu_threshold) / max(1.0, 100.0 - self._cpu_threshold))
            ram_excess = max(0.0, (sys_tel.ram_percent - self._ram_threshold) / max(1.0, 100.0 - self._ram_threshold))
            r_sys = min(1.0, 0.5 * cpu_excess + 0.5 * ram_excess)
        else:
            r_sys = 0.0

        # 5. Extract raw service times for latency min-max normalization
        latencies = [w.ewma_latency_ms if w.ewma_latency_ms is not None else 50.0 for w in eligible]
        min_lat = min(latencies)
        max_lat = max(latencies)
        lat_range = max_lat - min_lat

        # 6. Evaluate normalized cost function for each eligible worker
        best_worker = None
        min_cost = float("inf")

        for idx, w in enumerate(eligible):
            # A. Load score L_w in [0, 1]
            backlog = w.active_requests + w.queued_requests
            l_score = min(1.0, backlog / float(w.max_queue_size))

            # B. Normalized latency score T_w in [0, 1]
            raw_lat = latencies[idx]
            t_score = (raw_lat - min_lat) / lat_range if lat_range > 0.0 else 0.0

            # C. Operational health multiplier H_w
            w_state = w.state
            if w_state == WorkerState.DEGRADED:
                h_weight = 0.5
            else:
                h_weight = 1.0

            # D. Total Cost: Cost(w, r) = (w_L * L + w_T * T + w_R * R_sys) / H_w
            cost = (self._w_load * l_score + self._w_latency * t_score + self._w_system * r_sys) / h_weight

            if cost < min_cost:
                min_cost = cost
                best_worker = w

        return best_worker
