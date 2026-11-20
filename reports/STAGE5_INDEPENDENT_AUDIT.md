# SETU-NETRA Stage 5 Independent Technical Audit
## Comprehensive Reliability, Distributed Concurrency, Mathematical Correctness, and Benchmarking Audit

**Document Reference**: AUDIT-STAGE5-SYS-001  
**Auditor Roles**: Senior Distributed Systems Engineer, AI Inference Infrastructure Engineer, Software Reliability Auditor  
**Project**: SETU-NETRA (Bridge-Eye) — Intelligent Document Understanding, Grounded QA, and Adaptive Model Orchestration  
**Audit Target**: Stage 5 — Adaptive Model Routing & Intelligent Traffic Management  
**Date**: November 2026  
**Repository Working Directory**: `D:\Projects\Setu-Netra`  
**Execution Environment**: Windows 11 Home 64-bit, Intel Core i5-1334U CPU (10 Cores: 2 P-Cores, 8 E-Cores, 12 Threads), 16.0 GB Physical RAM, Python 3.14.0, PyTorch 2.6.0+cpu  

---

## 1. Executive Assessment

This independent technical audit evaluated the Stage 5 implementation of SETU-NETRA, focusing on the newly introduced **Adaptive Model Router**, **Inference Worker Pool**, **Traffic Schedulers (6 algorithms)**, **Genuine Host Telemetry Engine**, and **End-to-End Orchestration Pipeline**.

### Key Findings
1. **Architectural Decoupling**: **VERIFIED**. The system achieves strict architectural decoupling between *Model Selection* (what model executes the task based on intent, SLA, evidence, and capabilities) and *Worker Scheduling* (which worker instance executes the task based on load, hardware contention, and worker health).
2. **Scheduler Implementation & Concurrency**: **VERIFIED WITH OBSERVATIONS**. All 6 schedulers (`RoundRobin`, `Random`, `LeastOutstanding`, `SECT`, `CapacityAware`, `AdaptiveResilient`) are implemented and functioning. Concurrency is thread-safe across workers using bounded FIFO queues and `RLock`. However, concurrency within an individual worker thread is strictly serial (concurrency limit = 1).
3. **Hardware Telemetry Validity**: **PARTIALLY VERIFIED / CRITICAL DEFECT ON NON-WINDOWS**. On Windows, telemetry reads genuine OS kernel counters via standard-library `ctypes` (`GlobalMemoryStatusEx`, `GetSystemTimes`). However, contrary to file docstring claims, **no Linux `/proc/meminfo` or CPU reader exists**. On Linux/macOS, the module falls back to hardcoded values (15% CPU, 50% RAM) while falsely setting `is_real = True`.
4. **Benchmark Validity**: **PARTIALLY VERIFIED (MICROBENCHMARK ONLY)**. The benchmark harness (`benchmarks/run_traffic_benchmark.py`) is a synthetic scheduler microbenchmark utilizing calibrated `time.sleep()` delays and synthetic failure injection. It does **not** evaluate live neural model inference (EasyOCR, MiniLM, SmolLM2). The reported **346.3 req/s** measures multi-threaded dispatch of an 8 ms sleep workload, not real LLM inference.
5. **Model Routing Quality & Reasoning Claims**: **PARTIALLY VERIFIED / CAPABILITY MISATTRIBUTION**. The deterministic routing, SLA filtering, evidence grounding, and task rejections are mathematically and logically sound. However, registering `SmolLM2-135M-Instruct` as a "reasoning engine" with 0.85 confidence for complex reasoning tasks is an unsubstantiated capability claim. A 134.5M parameter SLM cannot reliably perform multi-hop deductive reasoning.
6. **Regression & Software Stability**: **VERIFIED**. The entire 149-test suite passes with 0 failures, 0 errors, and 0 regressions.

---

## 2. Verified Implementation Details

The audit inspected and verified the following core components across the repository:

| Component | Source File | Core Class / Method | Verification Status |
| :--- | :--- | :--- | :--- |
| **Contracts & Envelopes** | [`src/setu_netra/routing/contracts.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/contracts.py) | `InferenceRequest`, `InferenceResponse`, `RoutingDecision`, `SchedulingDecision`, `WorkerState` | **VERIFIED** |
| **Adaptive Model Router** | [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py) | `AdaptiveModelRouter.route()` | **VERIFIED** |
| **Inference Worker** | [`src/setu_netra/routing/worker_pool.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/worker_pool.py) | `InferenceWorker._worker_loop()`, `submit()` | **VERIFIED** |
| **Inference Worker Pool** | [`src/setu_netra/routing/worker_pool.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/worker_pool.py) | `InferenceWorkerPool.create_worker()`, `get_workers_for_model()` | **VERIFIED** |
| **Base Scheduler Interface**| [`src/setu_netra/routing/schedulers/base.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/base.py) | `BaseScheduler.schedule()` | **VERIFIED** |
| **Round Robin Scheduler** | [`src/setu_netra/routing/schedulers/round_robin.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/round_robin.py) | `RoundRobinScheduler.select_worker()` | **VERIFIED** |
| **Random Scheduler** | [`src/setu_netra/routing/schedulers/random_scheduler.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/random_scheduler.py) | `RandomScheduler.select_worker()` | **VERIFIED** |
| **Least Outstanding Requests**| [`src/setu_netra/routing/schedulers/least_outstanding.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/least_outstanding.py) | `LeastOutstandingRequestsScheduler.select_worker()` | **VERIFIED** |
| **Predictive SECT Scheduler**| [`src/setu_netra/routing/schedulers/predictive.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/predictive.py) | `ShortestEstimatedCompletionTimeScheduler.estimate_completion_time()` | **PARTIALLY VERIFIED** |
| **Capacity-Aware Scheduler** | [`src/setu_netra/routing/schedulers/capacity_aware.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/capacity_aware.py) | `CapacityAwareScheduler.select_worker()` | **PARTIALLY VERIFIED** |
| **Adaptive Resilient Scheduler**| [`src/setu_netra/routing/schedulers/adaptive_resilient.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/adaptive_resilient.py) | `AdaptiveResilientScheduler.execute_with_resilience()` | **VERIFIED** |
| **Hardware Telemetry** | [`src/setu_netra/routing/system_telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/system_telemetry.py) | `SystemTelemetryProvider.get_telemetry()` | **PARTIALLY VERIFIED** |
| **Intelligent Pipeline** | [`src/setu_netra/routing/pipeline.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/pipeline.py) | `IntelligentInferencePipeline.execute()` | **VERIFIED** |

---

## 3. Architectural Correctness

### 3.1 Model Selection vs. Worker Scheduling Decoupling
- **Inspection of Router**: In [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py), lines 39–320, `AdaptiveModelRouter.route()` evaluates solely:
  - Task taxonomy (`request.task_type`)
  - Cognitive intent (`request.metadata['intent']` or derived via `classify_question_intent`)
  - Evidence requirement (`EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS`)
  - Quality requirement (`QualityRequirement.HIGH_PRECISION`)
  - Latency SLA (`request.timeout_ms`)
  - Model operational availability in the registry (`meta.availability`)
- The output is strictly a `RoutingDecision` (`selected_model_id`, `confidence`, `reason`, `fallback_model_id`, `status`).
- **Zero Worker Coupling**: `AdaptiveModelRouter` does not instantiate, reference, or select worker instances or worker queues.

### 3.2 Two-Phase Pipeline Execution
- In [`src/setu_netra/routing/pipeline.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/pipeline.py), the execution sequence in `execute()` follows a strict two-phase pipeline:
  1. **Phase 1 (Model Selection)**: Line 111: `routing_decision = self._router.route(request)`.
  2. **Worker Pool Resolution**: Line 137: `candidate_workers = self._worker_pool.get_workers_for_model(selected_model_id, available_only=True)`.
  3. **Phase 2 (Worker Scheduling)**: Lines 162/166: Scheduler is invoked on `candidate_workers`.
- If no workers exist for a selected registered model, lines 141–144 dynamically spawn a worker for that adapter.

### 3.3 Request Correlation ID & Metadata Traceability
- **Request ID Invariance**: Line 96 extracts `req_id = request.request_id`. Lines 246–276 construct the final `InferenceResponse` preserving `request_id=req_id`.
- Early rejections (line 114) and worker scheduling failures (line 170) preserve `req_id`.
- **Metadata Preservation**: The response metadata accumulates:
  - Worker attribution: `worker_id` and `queue_wait_ms`
  - Epistemic status: `citations`, `epistemic_status` (`EVIDENCE_BACKED`, `UNSUPPORTED`, `GENERAL_KNOWLEDGE`)
  - Routing provenance: `selected_model`, `task_type`, `confidence`, `reason`
  - Scheduling provenance: `strategy`, `worker_id`
  - System telemetry: `cpu_percent`, `ram_percent`, `avail_ram_mb`

### 3.4 Preservation of Stages 1–4 Functionality
- All existing document ingestion (PDF, DOCX, TXT, images), EasyOCR CRAFT+CRNN detection, XY-cut spatial column reconstruction, Sentence Transformers 384-dim embeddings, SQLite BLOB defense mechanisms, and hybrid RRF retrieval continue to operate without modification.

---

## 4. Mathematical Correctness of Schedulers

### 4.1 Round Robin & Random
- **Round Robin**: Uses cyclical pointer arithmetic per model ID:
  $$\text{index} = \text{ptr} \pmod{|\text{candidates}|}, \quad \text{ptr} \leftarrow (\text{ptr} + 1) \pmod{|\text{candidates}|}$$
  Thread-safe via `self._lock` in [`round_robin.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/round_robin.py#L36-L40).
- **Random**: Uniform stochastic selection via `random.Random(seed).choice(candidates)`.

### 4.2 Least Outstanding Requests (LOR)
- **Mathematical Specification**:
  $$w^* = \arg\min_{w \in \mathcal{W}} (A_w + Q_w)$$
- **Code Verification**: In [`least_outstanding.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/least_outstanding.py#L33-L47):
  ```python
  min_load = best_worker.active_requests + best_worker.queued_requests
  for w in candidates[1:]:
      load = w.active_requests + w.queued_requests
      if load < min_load:
          min_load = load
          best_worker = w
  ```
- **Tie-Breaking**: When loads are equal, it compares `w.ewma_latency_ms`, prioritizing historically faster workers.
- **Verdict**: **VERIFIED**.

### 4.3 Shortest Estimated Completion Time (SECT)
- **Mathematical Specification**:
  $$\text{ECT}(w, r) = \text{WaitTime}(w) + \text{ExecTime}(w, r)$$
  $$\text{WaitTime}(w) = (A_w + Q_w) \cdot \hat{T}_{\text{exec}}(w, r)$$
- **Input Scaling Implementation**: In [`predictive.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/predictive.py#L50-L64):
  - For non-generative models:
    $$\text{scale} = 1.0 + \max\left(0, \frac{\text{token\_count} - 100}{500}\right)$$
  - For generative models:
    $$\text{exec\_ms} = \frac{\text{target\_new\_tokens}}{\text{throughput}} \times 1000.0$$
- **Defects / Approximations in SECT**:
  1. **Generative Prompt Prefill Neglected**: The generative branch ignores `token_count` of the prompt. It estimates latency purely on output tokens: $\text{target\_new\_tokens} / \text{throughput}$. On CPU, prefill latency scales linearly with prompt length.
  2. **Homogeneous Queue Service Time Assumption**: `queue_wait_ms = backlog * service_time_ms` assumes every request currently queued in front of $r$ will take the exact same time as request $r$. A queued 500-token prompt is assumed to execute in the time of a 10-token prompt.
- **EWMA Initialization & Cold-Start**:
  - `worker.ewma_latency_ms` initializes to `None`.
  - Fallback sequence: `worker.ewma_latency_ms` $\to$ `adapter.metadata.measured_latency['mean_ms']` $\to$ Category heuristic defaults (2500ms Generative, 2.0ms Extractive, 1.0ms Classification, 15.0ms Embedding, 50.0ms generic).
  - Updates on success with $\alpha = 0.2$:
    $$\bar{T}_{t} = 0.2 \cdot T_{\text{measured}} + 0.8 \cdot \bar{T}_{t-1}$$
- **Verdict**: **PARTIALLY VERIFIED**.

### 4.4 Capacity-Aware Scheduling (CAS)
- **Cost Function Specification**:
  $$\text{Cost}(w, r) = \frac{w_L \cdot L_w + w_T \cdot T_w + w_R \cdot R_{\text{sys}}}{H_w}$$
- **Code Inspection** in [`capacity_aware.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/capacity_aware.py#L30-L111):
  - **Weight Normalization**: Sums to 1.0:
    $$w_L = \frac{0.50}{1.0}, \quad w_T = \frac{0.30}{1.0}, \quad w_R = \frac{0.20}{1.0}$$
  - **Queue Backlog Normalization**:
    $$L_w = \min\left(1.0, \frac{A_w + Q_w}{Q_{\max}}\right) \in [0, 1]$$
  - **Latency Normalization**:
    $$T_w = \frac{\text{raw\_lat} - \min(\text{lat})}{\max(\text{lat}) - \min(\text{lat})} \quad (\text{if range} > 0 \text{ else } 0.0)$$
    Guarded against division by zero when all workers have identical latencies.
  - **System Pressure Normalization**:
    $$\text{cpu\_excess} = \max\left(0, \frac{U_{\text{cpu}} - \theta_{\text{cpu}}}{\max(1.0, 100 - \theta_{\text{cpu}})}\right)$$
    $$\text{ram\_excess} = \max\left(0, \frac{U_{\text{ram}} - \theta_{\text{ram}}}{\max(1.0, 100 - \theta_{\text{ram}})}\right)$$
    $$R_{\text{sys}} = \min(1.0, 0.5 \cdot \text{cpu\_excess} + 0.5 \cdot \text{ram\_excess})$$
  - **Degraded Penalty**: $H_w = 0.5$ for `WorkerState.DEGRADED`, doubling the cost ($Cost / 0.5 = 2 \times Cost$).
  - **Hard Constraints**:
    - Host available RAM must satisfy model minimum requirement (`sys_tel.avail_ram_mb < min_ram_req_mb` $\to$ reject).
    - Queue saturation check: $A_w + Q_w \ge Q_{\max} \to$ exclude worker.
- **Single-Node Structural Limitation**:
  - Because all worker threads currently execute on the **same local host OS**, $R_{\text{sys}}$ is identical for all candidate workers in a given scheduling decision. $w_R \cdot R_{\text{sys}}$ acts as a uniform additive offset across all workers. It does not alter relative ranking between workers on the same machine.
- **Verdict**: **PARTIALLY VERIFIED**.

### 4.5 Adaptive Resilient Scheduler (ARS)
- **Circuit Breaker Transitions**:
  - Tracks consecutive failures per worker (`self._failures[worker_id]`).
  - When failures reach `max_consecutive_failures` (default 3), worker enters `COOLING_DOWN` with `cooldown_expiry = time.time() + cooldown_sec` (default 5.0s).
  - Also invokes `selected.trigger_cooldown(self._cooldown_sec)` on the worker instance.
- **Exclusion in `select_worker`**:
  - `is_cooling_down(w.worker_id)` filters cooling-down workers out of candidate pool.
  - When cooldown expires, failure count is reset to 0, readmitting the worker for probing.
- **Bounded Retries & Alternative Workers**:
  - In `execute_with_resilience` ([`adaptive_resilient.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/adaptive_resilient.py#L126-L163)):
    - `attempt_limit = (self._max_retries + 1) if is_idempotent else 1`
    - Maintains `tried_worker_ids = set()`.
    - Guarantees failed requests are **never** retried on the worker that just failed them.
- **Idempotency Guard**:
  - When `request.metadata['idempotent'] == False`, `attempt_limit` is strictly 1. Zero retries are performed.
- **Verdict**: **VERIFIED**.

---

## 5. Concurrency and Worker Lifecycle Findings

### 5.1 Thread Safety Analysis
- **Synchronization Primitives**:
  - `InferenceWorker`: Uses `threading.RLock()` guarding `_state`, `_active_requests`, `_failure_count`, and `_ewma_latency_ms`.
  - `InferenceWorkerPool`: Uses `threading.RLock()` guarding worker registries and model-to-worker mapping.
  - `AdaptiveResilientScheduler`: Uses `threading.RLock()` guarding `_failures` and `_cooldown_expiry`.
  - `RoundRobinScheduler`: Uses `threading.RLock()` guarding cyclic index pointers.
- **Queue Synchronization**: Uses `queue.Queue(maxsize=max_queue_size)`, which is fully synchronized and thread-safe.

### 5.2 Worker Concurrency Semantics
- **Worker Concurrency Limit**:
  - In `InferenceWorker.__init__`, `self._concurrency_limit` is stored (default 1).
  - However, each `InferenceWorker` launches exactly **one** daemon thread (`self._thread = threading.Thread(target=self._worker_loop, ...)`).
  - Therefore, concurrency within an individual `InferenceWorker` instance is **strictly 1** (serial execution from FIFO queue).
  - Multi-request concurrency is achieved exclusively by instantiating **multiple worker instances** (`worker_1`, `worker_2`) for a model.
- **Multi-Core Parallelism & Python GIL**:
  - When multiple workers run concurrently on multi-core CPUs:
    - Pure Python adapters (e.g., regex extractive QA, classification) contend for the Python GIL and run interleaved.
    - Neural adapters (PyTorch CPU / OpenMP / MKL in Sentence Transformers and SmolLM2) release the GIL during C++ GEMM matrix multiplications, achieving genuine multi-core parallel execution.

### 5.3 Dual-Phase Timeout Enforcement
- **Phase 1 (Queue Waiting Timeout)**: Lines 163–176 of `worker_pool.py`:
  If `queue_wait_ms > max_allowed_ms`, request is popped, discarded without executing, and returns `status="TIMEOUT"`.
- **Phase 2 (Total Execution Timeout)**: Lines 195–200:
  If `queue_wait_ms + exec_elapsed_ms > max_allowed_ms`, response is marked `status="TIMEOUT"`.

### 5.4 Graceful Shutdown
- `InferenceWorker.stop(drain=True, timeout=5.0)`:
  - Sets `self._running = False` and `self._state = WorkerState.STOPPED`.
  - If `drain=True`, waits up to `timeout` seconds for `_queue.empty()`.
  - Joins worker thread with 1.0s timeout.
- `InferenceWorkerPool.stop_all()` safely iterates over all registered workers and terminates threads cleanly.

---

## 6. Hardware Telemetry Findings

### 6.1 Telemetry Implementation Analysis
- Code: [`src/setu_netra/routing/system_telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/system_telemetry.py).
- **Windows Implementation**:
  - Uses `ctypes.windll.kernel32.GlobalMemoryStatusEx` and `GetSystemTimes`.
  - Reads `stat.dwMemoryLoad` (RAM percentage), `stat.ullAvailPhys` (available RAM), and `stat.ullTotalPhys` (total physical RAM).
  - Computes CPU utilization over intervals $\ge 0.05$s:
    $$\Delta \text{total} = t_2 - t_1, \quad \Delta \text{idle} = i_2 - i_1$$
    $$\text{cpu\_percent} = \left(1.0 - \frac{\Delta \text{idle}}{\Delta \text{total}}\right) \times 100.0$$
  - Rate-limited with `cache_ttl_sec = 0.5`.
  - **Empirical Host Verification**: Live queries return host CPU: 15.0%, RAM: 74.0%, Available RAM: 4,060 MB.

### 6.2 Critical Defect: Non-Windows Platform Behavior
- The module docstring claims:
  > *"Provides real hardware resource telemetry directly from the operating system kernel via Python's standard library ctypes (Windows) or /proc/meminfo (Linux)... Adheres strictly to zero-simulation mandates."*
- **Source Inspection Reveals**:
  - Lines 31–59 define Windows API bindings.
  - **No `/proc/meminfo` or `/proc/stat` implementation exists.**
  - On Linux or macOS, `_HAS_WINDOWS_API` evaluates to `False`.
  - In `get_telemetry()`, lines 94–98 initialize:
    ```python
    cpu_pct = 15.0
    ram_pct = 50.0
    avail_mb = 4096.0
    total_mb = 16384.0
    ```
  - The `if _HAS_WINDOWS_API:` block is skipped.
  - Line 127 constructs `SystemTelemetry(..., is_real=True)`.
- **Verdict**: On Linux/macOS, hardware metrics are **hardcoded synthetic values** while being falsely reported as `is_real=True`. This is a critical defect for non-Windows environments.

### 6.3 Thread Safety of Telemetry Provider
- `SystemTelemetryProvider` does not use a mutex around `_last_sample`, `_last_idle_time`, and `_last_total_time`.
- High-concurrency calls can cause race conditions updating `_last_cpu_sample_time`, leading to intermittent $\Delta \text{total} \le 0$ conditions. While handled by line 118 (`elif self._last_sample:`), thread synchronization should be added.

---

## 7. Benchmark Validity Findings

### 7.1 Benchmark Nature: Synthetic Microbenchmark vs. Real Inference
- Inspection of [`benchmarks/run_traffic_benchmark.py`](file:///d:/Projects/Setu-Netra/benchmarks/run_traffic_benchmark.py):
  - Lines 59–125 define `BenchmarkModelAdapter`:
    ```python
    def execute(self, request: InferenceRequest) -> InferenceResponse:
        exec_ms = request.metadata.get("target_latency_ms", self._base_latency_ms)
        if exec_ms > 0:
            time.sleep(exec_ms / 1000.0)
        if self._failure_rate > 0.0 and random.random() < self._failure_rate:
            raise RuntimeError(f"Injected transient failure on {self._worker_id}")
        return InferenceResponse(...)
    ```
- **Finding**: The benchmark harness does **NOT** execute real AI models. It uses **Category B/C: Lightweight synthetic adapters with calibrated `time.sleep()` delays and synthetic random failures**.
- **Reasoning**: This is appropriate for a *traffic scheduling microbenchmark* (isolating queue wait times, thread dispatch overhead, and circuit breaking from neural model compute time).
- **Separation of Concerns**: It is critical to state that these benchmarks evaluate **scheduler coordination capacity**, not end-to-end model inference throughput.

### 7.2 Investigation of Reported 346.3 req/s Throughput
- In `TRAFFIC_BENCHMARK_RESULTS.md`, Least Outstanding Requests (LOR) reports **346.3 req/s** under the `burst` workload.
- **How 346.3 req/s was produced**:
  - Workload: `burst` (30 requests).
  - Worker topology: 3 workers (`w1`, `w2`, `w3`) each with `latency_ms = 8.0` ms.
  - Client dispatch: `ThreadPoolExecutor(max_workers=16)` concurrently submitting requests.
  - With 3 parallel worker threads each sleeping for 8 ms, theoretical capacity is:
    $$\text{Capacity} = \frac{3 \text{ workers}}{0.008 \text{ s}} = 375 \text{ req/s}$$
  - The measured wall-clock time was **0.0866 seconds** for 30 requests:
    $$\text{Throughput} = \frac{30}{0.0866} = 346.3 \text{ req/s}$$
- **Verification**: The 346.3 req/s throughput genuinely represents the dispatch and execution rate of the **multi-threaded scheduler managing an 8 ms synthetic payload across 3 workers**. It does **not** represent neural LLM generation throughput.

### 7.3 Investigation of Reported 11.2 ms Failover
- In `demonstrate_stage5.py`, an end-to-end failover dispatch completed in **11.2 ms**.
- **Source Inspection of Demo**:
  - Request: `sample_req` targeting `grounded-extractive-qa-v1` with a 1-sentence context passage.
  - Worker 1 (`w_qa_1`) was pre-emptively placed in `COOLING_DOWN` (`w_qa_1.trigger_cooldown(3.0)`).
  - `AdaptiveResilientScheduler.select_worker()` detected that `w_qa_1` was in cooldown, excluded it, and selected `w_qa_2` on attempt 0.
  - `w_qa_2` executed `GroundedExtractiveQAAdapter` (regex/substring search over a 1-sentence passage), which takes ~1.0 ms.
  - Total elapsed time: ~1.0 ms inference + ~10.2 ms for scheduler routing, thread queue handoff, citation verification, and OS ctypes telemetry query.
- **Verification**: The 11.2 ms result is **genuine**, but it measures:
  1. **Proactive avoidance** of an already cooling-down worker (0 retries required).
  2. Ultra-fast **extractive QA** over a single in-memory sentence.
  3. It does **not** measure mid-flight crash recovery of a 2.5-second generative SLM.

---

## 8. Model Routing Quality Findings

### 8.1 Evaluated Routing Policies
- **Deterministic Routing**: OCR $\to$ `easyocr-craft-crnn`, Embedding $\to$ `sentence-transformers/all-MiniLM-L6-v2`, Classification $\to$ `academic-domain-classifier-v1`. (VERIFIED)
- **SLA Enforcement**: Generative QA requests with `timeout_ms < 1500` ms fall back to Extractive QA (~1 ms) or are rejected, protecting the pipeline from SLA breaches. (VERIFIED)
- **Evidence Requirements**: `EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS` routes directly to `grounded-extractive-qa-v1` for zero-hallucination provenance. (VERIFIED)
- **Unsupported Task Rejection**: Tasks without registered adapters (`video_generation`, `quantum_teleportation`) return `status="REJECTED"` with 0.0 confidence. (VERIFIED)
- **Degraded/Unavailable Fallback**: When an explicit target model is marked `UNAVAILABLE`, the router searches for healthy fallback adapters serving the same task category. (VERIFIED)

### 8.2 Critical Finding: Reasoning Capability Misattribution
- In [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py), lines 253–272:
  ```python
  if task_type == "reasoning":
      if generative_id and max_latency_ms >= 2000.0:
          return RoutingDecision(
              selected_model_id=generative_id,
              task_type="reasoning",
              confidence=0.85,
              reason="Routed to local SLM for comparative reasoning.",
              fallback_model_id=extractive_id,
              status="ROUTED",
          )
  ```
- **Defect Analysis**:
  - The router assigns `SmolLM2-135M-Instruct` to handle `reasoning` tasks with **0.85 confidence**.
  - `SmolLM2-135M-Instruct` is a 134.5M parameter Small Language Model. While competent at concise comparative descriptions (e.g., QuickSort vs. MergeSort definitions), models below 1B parameters cannot perform reliable multi-hop reasoning, symbolic deduction, or multi-step arithmetic over documents.
  - Assigning high routing confidence (0.85) to a 135M SLM for general reasoning without grounding or verification constitutes **capability misattribution**.
  - **Remediation**: For reasoning tasks, routing confidence should be downgraded (e.g., 0.50) with an explicit routing caveat in metadata, or routed to a hybrid verification pipeline requiring extractive evidence grounding.

---

## 9. Regression Test Results

The complete automated test suite was executed in verbose mode using the project's virtual environment:
```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

### 9.1 Summary Statistics
- **Total Test Cases Executed**: 149
- **Passed**: 149 (100.0%)
- **Failed**: 0 (0.0%)
- **Errors**: 0 (0.0%)
- **Skipped**: 0 (0.0%)
- **Execution Wall Clock Time**: 23.084s (standard discovery) / 98.953s (verbose mode)
- **Regressions**: 0

### 9.2 Test Suite Composition Audit

| Test Module | Test Count | Nature of Tests (Real vs. Mocked) | Audit Observation |
| :--- | :---: | :--- | :--- |
| `tests.test_adaptive_router` | 8 | Real router logic with registered adapters | Exercises actual routing rules, SLA filtering, fallback, and task rejections. |
| `tests.test_worker_pool` | 6 | Real threads with synthetic adapters | Validates thread loops, queues, timeouts, backpressure, and circuit breakers. |
| `tests.test_schedulers` | 7 | Real schedulers with synthetic workers | Validates RR, Random, LOR, SECT, CAS, and ARS algorithms. |
| `tests.test_traffic_pipeline` | 4 | Real pipeline with real & synthetic adapters | Validates end-to-end execution, scheduler swapping, and fault recovery. |
| `tests.test_model_registry` | 9 | Real ModelRegistry instance | Validates thread safety, worker pooling, telemetry tracking, and P95 latency. |
| `tests.test_inference_interface` | 7 | Real adapters & contracts | Validates unified contracts, lazy loading, and adapter execution. |
| `tests.test_grounded_qa_engine` | 5 | Real extractive QA engine | Validates evidence matching, citation verification, and epistemic abstention. |
| `tests.test_question_extractor` | 9 | Real regex & NLP extractor | Validates single/multi questions, MCQ parsing, and cognitive intent. |
| `tests.test_docx_txt_ingestion` | 7 | Real file parsing | Validates DOCX and TXT extraction and block provenance. |
| `tests.test_xy_cut_layout` | 4 | Real spatial algorithm | Validates recursive XY-cut column splitting and gutter detection. |
| `tests.test_semantic` | 8 | Real PyTorch weights + offline hashing | Loads genuine 384-dim SentenceTransformer weights (`all-MiniLM-L6-v2`). |
| `tests.test_embedding_corruption` | 8 | Real SQLite DB with corrupted BLOBs | Validates NaN, Inf, and dimension mismatch defenses in SQLite store. |
| `tests.test_hybrid_score_robustness` | 6 | Real retrieval mathematics | Validates BM25, Cosine, and RRF normalization under score edge cases. |
| `tests.test_duplicate_suppression` | 9 | Real retrieval deduplication | Validates SHA-256 block deduplication and near-duplicate suppression. |
| `tests.test_milestone5` | 36 | Comprehensive M1–M5 tests | Validates end-to-end ingestion, OCR, layout, indexing, and search. |
| `tests.test_ingestion`, `test_ocr`, `test_structure` | 16 | Foundational components | Core unit tests for geometry, bounding boxes, and base contracts. |
| **TOTAL** | **149** | **Mixed Real & Synthetic** | **100% Pass Rate Verified** |

---

## 10. Critical Defects

1. **Missing Linux Telemetry Implementation (False Real Telemetry Claim)**:
   - *File*: [`src/setu_netra/routing/system_telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/system_telemetry.py#L94-L128)
   - *Defect*: The docstring explicitly claims Linux support via `/proc/meminfo`. In reality, no Linux `/proc` parsing exists. On non-Windows platforms, hardcoded values (15% CPU, 50% RAM, 4096 MB RAM) are returned with `is_real=True`.
   - *Impact*: On Linux servers or Docker containers, capacity-aware scheduling operates on fabricated static numbers.
   - *Severity*: **CRITICAL (Portability & Correctness)**.

2. **Reasoning Capability Misattribution to 135M Parameter SLM**:
   - *File*: [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py#L253-L263)
   - *Defect*: Router assigns `SmolLM2-135M-Instruct` to handle general `reasoning` tasks with 0.85 confidence without grounding verification.
   - *Impact*: 135M parameter models produce hallucinations and invalid deduction chains on multi-step reasoning.
   - *Severity*: **CRITICAL (Epistemic Grounding)**.

---

## 11. Major Weaknesses

1. **SECT Latency Estimation Ignores Generative Prompt Prefill**:
   - *File*: [`src/setu_netra/routing/schedulers/predictive.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/predictive.py#L55-L60)
   - *Weakness*: For generative models, service time is calculated solely as `target_new_tokens / throughput * 1000`. Prompt length (`token_count`) is completely omitted. A 2,000-token prompt has significant CPU prefill latency that SECT completely ignores.

2. **Single-Node Redundancy of Host Telemetry in Capacity-Aware Cost Function**:
   - *File*: [`src/setu_netra/routing/schedulers/capacity_aware.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/capacity_aware.py#L78-L82)
   - *Weakness*: Because all candidate workers reside on the same local host, $R_{\text{sys}}$ is identical for all candidate workers during a scheduling decision. It acts as an invariant additive scalar and does not differentiate between workers on the same machine.

3. **Concurrency Bottleneck within Individual Worker**:
   - *File*: [`src/setu_netra/routing/worker_pool.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/worker_pool.py#L59-L65)
   - *Weakness*: Each `InferenceWorker` has exactly one background thread. Requests queue up serially per worker. To achieve parallel throughput, the administrator must manually spawn multiple distinct `InferenceWorker` instances for each adapter.

4. **Synthetic Nature of Benchmarks Not Clearly Demarcated in Earlier Summaries**:
   - *File*: [`benchmarks/run_traffic_benchmark.py`](file:///d:/Projects/Setu-Netra/benchmarks/run_traffic_benchmark.py#L59-L125)
   - *Weakness*: The 346.3 req/s throughput was obtained using an 8 ms `time.sleep()` payload. Reporting this without explicitly labeling it as a *scheduler coordination microbenchmark* can mislead stakeholders into believing the local LLM generates 346 responses per second.

---

## 12. Minor Improvements

1. **Thread-Safety for SystemTelemetryProvider**:
   - Add a `threading.Lock()` in `SystemTelemetryProvider.get_telemetry()` to prevent multi-threaded race conditions when reading and updating `_last_idle_time` and `_last_total_time`.
2. **In-Flight Queue Service Time Estimation in SECT**:
   - Instead of multiplying `backlog * service_time_ms(incoming_request)`, SECT should track the cumulative estimated remaining time of the items actually sitting in the queue.
3. **Speculative Execution Cancellation on Retry**:
   - In `AdaptiveResilientScheduler`, if a worker times out and the request is retried on an alternative worker, the original worker thread continues executing the adapter to completion in the background. A cancellation token or `Future.cancel()` mechanism should be added to abort abandoned execution.

---

## 13. Evidence References

| Evidence ID | Code Entity | File Location | Line Numbers | Verified Characteristic |
| :--- | :--- | :--- | :--- | :--- |
| **EV-01** | `AdaptiveModelRouter.route` | [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py) | L39–L320 | Model selection independent of worker selection. |
| **EV-02** | `InferenceWorkerPool.create_worker` | [`src/setu_netra/routing/worker_pool.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/worker_pool.py) | L295–L317 | Worker instantiation and pooling. |
| **EV-03** | `LeastOutstandingRequestsScheduler` | [`src/setu_netra/routing/schedulers/least_outstanding.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/least_outstanding.py) | L32–L47 | Exact formula $w^* = \arg\min (A_w + Q_w)$. |
| **EV-04** | `ShortestEstimatedCompletionTimeScheduler` | [`src/setu_netra/routing/schedulers/predictive.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/predictive.py) | L27–L71 | Input token scaling and completion time estimation. |
| **EV-05** | `CapacityAwareScheduler` | [`src/setu_netra/routing/schedulers/capacity_aware.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/capacity_aware.py) | L30–L111 | Multi-criteria normalized cost function with host RAM checks. |
| **EV-06** | `AdaptiveResilientScheduler` | [`src/setu_netra/routing/schedulers/adaptive_resilient.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/adaptive_resilient.py) | L113–L202 | Failover retries, idempotency guards, and alternate worker selection. |
| **EV-07** | `SystemTelemetryProvider` | [`src/setu_netra/routing/system_telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/system_telemetry.py) | L88–L130 | Windows `ctypes` bindings; fallback defaults on non-Windows. |
| **EV-08** | `BenchmarkModelAdapter` | [`benchmarks/run_traffic_benchmark.py`](file:///d:/Projects/Setu-Netra/benchmarks/run_traffic_benchmark.py) | L59–L125 | Calibrated `time.sleep()` microbenchmark harness. |
| **EV-09** | `IntelligentInferencePipeline.execute` | [`src/setu_netra/routing/pipeline.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/pipeline.py) | L83–L276 | Complete 7-stage request-to-response pipeline. |

---

## 14. Final Verdict

| Evaluation Category | Audit Verdict | Detailed Finding Summary |
| :--- | :--- | :--- |
| **Decoupled Architecture** | **VERIFIED** | Model selection and worker scheduling are completely independent and cleanly mediated by `IntelligentInferencePipeline`. |
| **Scheduling Mathematics** | **PARTIALLY VERIFIED** | LOR, RR, Random, and ARS are mathematically exact. SECT omits generative prompt prefill; CAS system cost is invariant across local workers. |
| **Worker Concurrency** | **VERIFIED** | Multi-worker concurrency, bounded FIFO queues, timeout enforcement, backpressure, and graceful shutdown function properly. |
| **Hardware Telemetry** | **PARTIALLY VERIFIED** | Real and accurate on Windows via OS `ctypes`. Missing Linux/macOS implementation (falls back to hardcoded 15% CPU / 50% RAM). |
| **Benchmark Validity** | **PARTIALLY VERIFIED** | Valid as a scheduler coordination microbenchmark. Does not measure real neural LLM/OCR inference throughput. |
| **Model Routing Quality** | **PARTIALLY VERIFIED** | Accurate for OCR, Embedding, Classification, and Extractive QA. Misattributes deep reasoning capabilities to 135M parameter SLM. |
| **Regression Testing** | **VERIFIED** | 149 of 149 tests pass in 23.08s with zero regressions across Milestones 1–5 and Stages 3–5. |
| **OVERALL STAGE 5 VERDICT** | **PARTIALLY VERIFIED** | The distributed scheduling and routing architecture is sound, robust, and passing all tests, but requires Linux telemetry implementation, benchmark scope clarification, and reasoning capability calibration. |

---

## 15. Prioritized Action List for Stage 6

Before proceeding to Stage 6, the following items must be addressed in order of priority:

1. **[HIGH] Implement Genuine Linux Telemetry**:
   - Implement `/proc/meminfo` (MemTotal, MemAvailable) and `/proc/stat` (CPU jiffies) parsing in [`system_telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/system_telemetry.py) so Linux deployments do not rely on hardcoded synthetic values.
2. **[HIGH] Clarify Benchmark Documentation & Scope**:
   - In all technical reports and presentations, explicitly label the 346.3 req/s figure as a *Scheduler Concurrency Microbenchmark* for an 8 ms synthetic payload. Clearly contrast this against the measured 15.0 tokens/s (~1.5 req/s) CPU throughput of `SmolLM2-135M-Instruct`.
3. **[HIGH] Recalibrate Reasoning Routing Confidence**:
   - Lower the routing confidence for `SmolLM2-135M-Instruct` on general reasoning tasks from 0.85 to $\le 0.50$, or require hybrid evidence grounding via `GroundedExtractiveQAAdapter`.
4. **[MEDIUM] Add Prompt Prefill Scaling to SECT**:
   - Update [`predictive.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/schedulers/predictive.py) so generative latency estimation accounts for input prompt token length in addition to generated tokens.
5. **[MEDIUM] Thread-Safe Telemetry Sampling**:
   - Wrap `SystemTelemetryProvider.get_telemetry()` with a `threading.Lock()` to prevent race conditions during high-frequency concurrent sampling.
