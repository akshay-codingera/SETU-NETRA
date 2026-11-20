"""
round_robin.py: Deterministic Round-Robin traffic scheduler.

Why this file exists:
Provides cyclic load distribution across healthy workers. Serves as a standard baseline.
"""

import threading
from typing import Dict, List, Optional

from setu_netra.routing.contracts import InferenceRequest
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.worker_pool import InferenceWorker


class RoundRobinScheduler(BaseScheduler):
    """Schedules requests sequentially across candidate workers."""

    def __init__(self):
        self._lock = threading.RLock()
        self._pointers: Dict[str, int] = {}

    @property
    def name(self) -> str:
        return "ROUND_ROBIN"

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None

        model_key = candidates[0].model_id
        with self._lock:
            ptr = self._pointers.get(model_key, 0)
            selected = candidates[ptr % len(candidates)]
            self._pointers[model_key] = (ptr + 1) % len(candidates)
            return selected
