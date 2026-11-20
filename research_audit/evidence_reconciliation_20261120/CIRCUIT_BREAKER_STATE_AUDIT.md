# SETU-NETRA Circuit Breaker and Worker Fault Isolation Audit

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Distributed Systems Engineer & Fault Resilience Auditor  
**Scope:** Circuit Breaker Finite State Machine (`CircuitBreaker`), Worker Pools, and Retry Idempotency  
**Primary Reference Files:**
- [`src/setu_netra/runtime/circuit_breaker.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/runtime/circuit_breaker.py)
- [`src/setu_netra/runtime/worker_pool.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/runtime/worker_pool.py)
- [`benchmarks/runners/reliability_runner.py`](file:///d:/Projects/Setu-Netra/benchmarks/runners/reliability_runner.py)
- [`benchmarks/results/aggregated/reliability_evaluation_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/reliability_evaluation_summary.json)

---

## 1. Circuit Breaker Finite State Machine Verification

The SETU-NETRA runtime manages inference worker resilience via a 3-state Circuit Breaker pattern implemented in `src/setu_netra/runtime/circuit_breaker.py`:

```
               +--------------------------------------+
               |                                      |
               v                                      | Success (Trial)
         +------------+      Failures >= Threshold    +---------------+
   ----->|   CLOSED   | ----------------------------> |     OPEN      |
         +------------+                               +---------------+
               ^                                              |
               |                                              | Cooldown Elapsed
               | Success (Probe)                              v
         +------------+                               +---------------+
         | HALF_OPEN  | <---------------------------- |   COOLDOWN    |
         +------------+                               +---------------+
               |
               | Failure (Probe)
               +---------------------------------------------> (Back to OPEN)
```

### Operational Parameters
- **Failure Threshold:** 3 consecutive worker errors.
- **Cooldown Duration:** 2.0 seconds.
- **Success Threshold (to close):** 1 successful execution during `HALF_OPEN`.

### State Audit Results (Test 04 in Reliability Suite)
- **Initial State:** `CircuitBreaker.state == CircuitState.CLOSED`.
- **Fault Injection:** 3 synthetic `RuntimeError` exceptions dispatched to worker `w_flaky`.
- **Tripping Action:** At failure count 3, circuit transitions to `CircuitState.OPEN`. Consecutive requests to `w_flaky` are fast-failed without invoking the underlying model adapter, saving CPU cycles.
- **Auto-Recovery Action:** After `cooldown_sec = 2.0`, circuit transitions to `CircuitState.HALF_OPEN`. A trial request succeeds, resetting failure count to 0 and restoring state to `CircuitState.CLOSED`.

---

## 2. Idempotency and Non-Retryable Task Safety

A critical architectural distinction verified in Test 05 is **idempotency-aware dispatch**:
- In standard RPC systems, naive retry loops on non-idempotent operations (e.g. state-mutating database operations or external API calls) can cause catastrophic duplicated executions.
- `InferenceRequest` incorporates a mandatory `is_idempotent: bool` flag.
- When `is_idempotent = False` and an execution fails, `AdaptiveResilientScheduler` **strictly suppresses all retries**, marking the response as `FAILED` after exactly 1 attempt (`attempts_performed == 1`).
- Only requests with `is_idempotent = True` (or read-only QA queries) are subject to exponential backoff and failover.

---

## 3. Resilience Scope: Local-First In-Process vs Distributed

### Reviewer Caveat & Scientific Boundary
While the circuit breaker and worker pool implementations are robust, their current realization operates **in-process using Python multi-threading (`concurrent.futures.ThreadPoolExecutor`)**:
- Worker communication occurs via local in-memory queues (`queue.Queue`).
- Failovers occur across thread-based worker wrappers on the same host machine.
- It does **not** employ a distributed consensus protocol (e.g. Raft, Paxos) or distributed message broker (e.g. Kafka, RabbitMQ).
- **Manuscript Correction:** Frame these mechanisms accurately as **"In-Process Asynchronous Worker Isolation and Circuit Breaking"** rather than "Distributed Enterprise Multi-Node Fault Tolerance".
