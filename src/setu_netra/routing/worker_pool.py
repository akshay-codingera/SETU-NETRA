"""
worker_pool.py: Multi-worker execution management subsystem for SETU-NETRA Stage 5.

Why this file exists:
Manages concrete InferenceWorker instances, background execution threads, request queues,
active request accounting (A_w), queue backlog tracking (Q_w), backpressure enforcement,
worker health probing, failure circuit breaking, and graceful worker shutdown.
Maintains strict separation between Model Selection (router.py) and Worker Scheduling (schedulers/).
"""

import concurrent.futures
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    WorkerState,
)
from setu_netra.routing.interfaces import BaseModelAdapter

logger = logging.getLogger(__name__)


class InferenceWorker:
    """Individual worker process/thread executing an underlying model adapter."""

    def __init__(
        self,
        worker_id: str,
        adapter: BaseModelAdapter,
        max_queue_size: int = 50,
        concurrency_limit: int = 1,
        failure_threshold: int = 3,
        cooldown_period_sec: float = 5.0,
    ):
        self._worker_id = worker_id
        self._adapter = adapter
        self._model_id = adapter.model_id
        self._max_queue_size = max_queue_size
        self._concurrency_limit = concurrency_limit
        self._failure_threshold = failure_threshold
        self._cooldown_period_sec = cooldown_period_sec

        self._lock = threading.RLock()
        self._state = WorkerState.IDLE
        self._active_requests = 0
        self._queue: queue.Queue[Tuple[InferenceRequest, concurrent.futures.Future, float]] = queue.Queue(maxsize=max_queue_size)
        
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._cooldown_until = 0.0
        self._ewma_latency_ms: Optional[float] = None
        self._total_processed = 0

        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=f"WorkerThread_{worker_id}",
            daemon=True,
        )
        self._thread.start()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def adapter(self) -> BaseModelAdapter:
        return self._adapter

    @property
    def state(self) -> str:
        with self._lock:
            # Check if cooldown period has elapsed
            if self._state == WorkerState.COOLING_DOWN and time.time() >= self._cooldown_until:
                self._state = WorkerState.IDLE if self._active_requests == 0 else WorkerState.BUSY
                self._failure_count = 0
            return self._state

    @property
    def active_requests(self) -> int:
        with self._lock:
            return self._active_requests

    @property
    def queued_requests(self) -> int:
        return self._queue.qsize()

    @property
    def max_queue_size(self) -> int:
        return self._max_queue_size

    @property
    def ewma_latency_ms(self) -> Optional[float]:
        with self._lock:
            return self._ewma_latency_ms

    @property
    def active_requests_count(self) -> int:
        return self.active_requests

    @property
    def queue_depth(self) -> int:
        return self.queued_requests

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def last_execution_latency_ms(self) -> Optional[float]:
        return self.ewma_latency_ms

    @property
    def is_cooling_down(self) -> bool:
        return self.state == WorkerState.COOLING_DOWN

    def is_available(self) -> bool:
        """Worker is available if running and not in FAILED, STOPPED, or active COOLING_DOWN state."""
        with self._lock:
            curr_state = self.state
            return (
                self._running
                and curr_state not in (WorkerState.FAILED, WorkerState.STOPPED, WorkerState.COOLING_DOWN)
                and self._adapter.is_available()
            )

    def is_healthy(self) -> bool:
        """Active health check of the worker and its adapter."""
        with self._lock:
            if not self._running or self._state in (WorkerState.FAILED, WorkerState.STOPPED):
                return False
            if self._state == WorkerState.COOLING_DOWN:
                if time.time() < self._cooldown_until:
                    return False
                self._state = WorkerState.IDLE
                self._failure_count = 0
            return self._adapter.health_check()

    def submit(self, request: InferenceRequest) -> concurrent.futures.Future[InferenceResponse]:
        """Submit an inference request to this worker's queue.

        Raises:
            queue.Full: When queue is at capacity (backpressure signal).
            RuntimeError: When worker is not running.
        """
        with self._lock:
            if not self._running:
                raise RuntimeError(f"Worker '{self._worker_id}' is stopped and cannot accept requests.")

            if not self.is_available():
                raise RuntimeError(f"Worker '{self._worker_id}' is unavailable (State: {self.state}).")

            # Check queue capacity for backpressure
            if self._queue.full():
                raise queue.Full(f"Worker '{self._worker_id}' queue is full (Max: {self._max_queue_size}).")

            future: concurrent.futures.Future[InferenceResponse] = concurrent.futures.Future()
            submit_time = time.time()
            self._queue.put_nowait((request, future, submit_time))
            return future

    def _worker_loop(self) -> None:
        """Background daemon processing thread."""
        while self._running:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            request, future, submit_time = item
            queue_wait_ms = (time.time() - submit_time) * 1000.0

            # 1. Check if request timed out while waiting in queue
            max_allowed_ms = request.timeout_ms if request.timeout_ms is not None else (request.timeout * 1000.0)
            if queue_wait_ms > max_allowed_ms:
                self._queue.task_done()
                timeout_resp = InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=self._model_id,
                    execution_time_ms=0.0,
                    status="TIMEOUT",
                    error=f"Request timed out waiting in worker queue ({queue_wait_ms:.1f}ms > {max_allowed_ms:.1f}ms).",
                    metadata={"worker_id": self._worker_id, "queue_wait_ms": round(queue_wait_ms, 2)},
                )
                future.set_result(timeout_resp)
                continue

            # 2. Enter active execution state
            with self._lock:
                self._active_requests += 1
                if self._state == WorkerState.IDLE:
                    self._state = WorkerState.BUSY

            exec_start = time.perf_counter()
            try:
                # Execute underlying model adapter
                response = self._adapter.execute(request)
                exec_elapsed_ms = (time.perf_counter() - exec_start) * 1000.0

                # Ensure metadata captures worker_id and queue wait
                response.metadata["worker_id"] = self._worker_id
                response.metadata["queue_wait_ms"] = round(queue_wait_ms, 2)

                # Check if total latency (queue + exec) exceeded timeout
                total_latency_ms = queue_wait_ms + exec_elapsed_ms
                if total_latency_ms > max_allowed_ms and response.status == "SUCCESS":
                    response.status = "TIMEOUT"
                    response.result = None
                    response.error = f"Total execution time ({total_latency_ms:.1f}ms) exceeded timeout limit of {max_allowed_ms:.1f}ms."

                # Update EWMA latency on success
                with self._lock:
                    if response.status == "SUCCESS":
                        self._failure_count = 0
                        if self._ewma_latency_ms is None:
                            self._ewma_latency_ms = exec_elapsed_ms
                        else:
                            alpha = 0.2
                            self._ewma_latency_ms = alpha * exec_elapsed_ms + (1.0 - alpha) * self._ewma_latency_ms
                        self._total_processed += 1
                    else:
                        self._handle_failure(response.error or "Inference failure")

                future.set_result(response)

            except Exception as err:
                exec_elapsed_ms = (time.perf_counter() - exec_start) * 1000.0
                with self._lock:
                    self._handle_failure(str(err))

                err_resp = InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=self._model_id,
                    execution_time_ms=round(exec_elapsed_ms, 2),
                    status="FAILED",
                    error=str(err),
                    metadata={"worker_id": self._worker_id, "queue_wait_ms": round(queue_wait_ms, 2)},
                )
                future.set_result(err_resp)

            finally:
                with self._lock:
                    self._active_requests = max(0, self._active_requests - 1)
                    if self._active_requests == 0 and self._state == WorkerState.BUSY:
                        self._state = WorkerState.IDLE
                self._queue.task_done()

    def _handle_failure(self, error_msg: str) -> None:
        """Circuit-breaker logic for consecutive worker failures."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        logger.warning(
            f"Worker '{self._worker_id}' experienced failure #{self._failure_count}: {error_msg}"
        )
        if self._failure_count >= self._failure_threshold:
            self._state = WorkerState.COOLING_DOWN
            self._cooldown_until = time.time() + self._cooldown_period_sec
            logger.error(
                f"Worker '{self._worker_id}' reached failure threshold ({self._failure_threshold}). "
                f"Entering COOLING_DOWN for {self._cooldown_period_sec}s."
            )

    def trigger_cooldown(self, duration_sec: Optional[float] = None) -> None:
        """Manually trigger worker cooldown."""
        with self._lock:
            dur = duration_sec or self._cooldown_period_sec
            self._state = WorkerState.COOLING_DOWN
            self._cooldown_until = time.time() + dur

    def stop(self, drain: bool = True, timeout: float = 5.0) -> None:
        """Stop worker processing loop gracefully."""
        with self._lock:
            self._running = False
            self._state = WorkerState.STOPPED

        if drain:
            deadline = time.time() + timeout
            while not self._queue.empty() and time.time() < deadline:
                time.sleep(0.05)

        if self._thread.is_alive():
            self._thread.join(timeout=1.0)


class InferenceWorkerPool:
    """Thread-safe centralized management subsystem for inference workers."""

    def __init__(self):
        self._lock = threading.RLock()
        self._workers: Dict[str, InferenceWorker] = {}
        self._model_workers: Dict[str, List[InferenceWorker]] = {}

    def register_worker(self, worker: InferenceWorker) -> None:
        """Add an instantiated InferenceWorker into the pool."""
        with self._lock:
            w_id = worker.worker_id
            m_id = worker.model_id
            self._workers[w_id] = worker
            if m_id not in self._model_workers:
                self._model_workers[m_id] = []
            if worker not in self._model_workers[m_id]:
                self._model_workers[m_id].append(worker)

    def create_worker(
        self,
        adapter: BaseModelAdapter,
        worker_id: Optional[str] = None,
        max_queue_size: int = 50,
        concurrency_limit: int = 1,
        failure_threshold: int = 3,
        cooldown_period_sec: float = 5.0,
    ) -> InferenceWorker:
        """Convenience method to construct, register, and start a worker for an adapter."""
        with self._lock:
            w_id = worker_id or adapter.worker_id or f"{adapter.model_id}_w{len(self.get_workers_for_model(adapter.model_id)) + 1}"
            worker = InferenceWorker(
                worker_id=w_id,
                adapter=adapter,
                max_queue_size=max_queue_size,
                concurrency_limit=concurrency_limit,
                failure_threshold=failure_threshold,
                cooldown_period_sec=cooldown_period_sec,
            )
            self.register_worker(worker)
            return worker

    def get_worker(self, worker_id: str) -> Optional[InferenceWorker]:
        """Retrieve worker instance by unique ID."""
        with self._lock:
            return self._workers.get(worker_id)

    def get_workers_for_model(self, model_id: str, available_only: bool = True) -> List[InferenceWorker]:
        """Retrieve all workers serving a specific model ID."""
        with self._lock:
            workers = self._model_workers.get(model_id, [])
            if available_only:
                return [w for w in workers if w.is_available()]
            return list(workers)

    def get_all_workers(self, available_only: bool = False) -> List[InferenceWorker]:
        """List all workers across all models."""
        with self._lock:
            if available_only:
                return [w for w in self._workers.values() if w.is_available()]
            return list(self._workers.values())

    # Convenience alias for pool inspection
    list_workers = get_all_workers


    def can_accept_request(self, model_id: str) -> bool:
        """Check if at least one available worker has queue capacity (backpressure check)."""
        with self._lock:
            workers = self.get_workers_for_model(model_id, available_only=True)
            if not workers:
                return False
            return any(w.queued_requests < w.max_queue_size for w in workers)

    def stop_all(self, drain: bool = True, timeout: float = 5.0) -> None:
        """Stop all workers in the pool gracefully."""
        with self._lock:
            workers = list(self._workers.values())

        for w in workers:
            w.stop(drain=drain, timeout=timeout)

        with self._lock:
            self._workers.clear()
            self._model_workers.clear()

    def get_pool_status(self) -> Dict[str, Any]:
        """Snapshot of current worker states, queue backlogs, and active counts."""
        with self._lock:
            status = {}
            for w_id, w in self._workers.items():
                status[w_id] = {
                    "model_id": w.model_id,
                    "state": w.state,
                    "active_requests": w.active_requests,
                    "queued_requests": w.queued_requests,
                    "max_queue_size": w.max_queue_size,
                    "ewma_latency_ms": round(w.ewma_latency_ms, 2) if w.ewma_latency_ms is not None else None,
                    "is_available": w.is_available(),
                }
            return status
