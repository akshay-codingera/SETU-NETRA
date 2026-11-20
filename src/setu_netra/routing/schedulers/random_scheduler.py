"""
random_scheduler.py: Uniform random traffic scheduler.

Why this file exists:
Dispatches requests uniformly at random across healthy workers. Serves as a stochastic baseline.
"""

import random
from typing import List, Optional

from setu_netra.routing.contracts import InferenceRequest
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.worker_pool import InferenceWorker


class RandomScheduler(BaseScheduler):
    """Schedules requests randomly across available candidate workers."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "RANDOM"

    def select_worker(
        self,
        request: InferenceRequest,
        candidates: List[InferenceWorker],
    ) -> Optional[InferenceWorker]:
        if not candidates:
            return None
        return self._rng.choice(candidates)
