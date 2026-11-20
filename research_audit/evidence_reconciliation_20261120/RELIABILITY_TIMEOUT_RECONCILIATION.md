# SETU-NETRA Reliability and Timeout Discrepancy Reconciliation Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Performance Benchmark & Reliability Auditor  
**Scope:** Stage 6 Reliability Benchmark, Timeout Thresholds, and Test Pass Interpretation  
**Primary Reference Files:**
- [`RELIABILITY_TEST_EVIDENCE.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/RELIABILITY_TEST_EVIDENCE.csv)
- [`CIRCUIT_BREAKER_STATE_AUDIT.md`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/CIRCUIT_BREAKER_STATE_AUDIT.md)
- [`benchmarks/runners/reliability_runner.py`](file:///d:/Projects/Setu-Netra/benchmarks/runners/reliability_runner.py)
- [`benchmarks/results/aggregated/reliability_evaluation_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/reliability_evaluation_summary.json)

---

## 1. Resolution of the Timeout Configuration Discrepancy

### The Discrepancy
- An earlier project report stated that the timeout reliability test evaluated a **50 ms task duration against a 10 ms SLA threshold**.
- The raw benchmark log `benchmarks/results/raw/reliability_evaluation_raw.json` reports:  
  `"Total execution time (300.4ms) exceeded timeout limit of 80.0ms."`

### Source Code Verification & Origin of Discrepancy
Direct inspection of `benchmarks/runners/reliability_runner.py` (lines 147–167, `test_02_execution_and_queue_timeouts`) reveals the ground-truth setup:

```python
def test_02_execution_and_queue_timeouts(self) -> Dict[str, Any]:
    pool = InferenceWorkerPool()
    w_slow = pool.create_worker(
        FaultyTestAdapter("w_slow", always_fail=False, sleep_ms=300.0),
        worker_id="w_slow",
    )
    req = InferenceRequest(task_type="reliability", input_payload="Timeout test", timeout=0.08)
    fut = w_slow.submit(req)
    resp = fut.result(timeout=1.0)
    ...
```

### Forensic Proof
1. The test deliberately instantiated `FaultyTestAdapter` with `sleep_ms = 300.0` (300 milliseconds of simulated computation).
2. The request specified `timeout = 0.08` seconds (80.0 milliseconds).
3. The execution elapsed 300.4 ms, which exceeded the 80.0 ms budget by 220.4 ms, triggering the worker's timeout guardrail and setting `resp.status = "TIMEOUT"`.
4. The citation of "50 ms task / 10 ms SLA" in prior documentation was an **illustrative design example** from early architecture specifications, not the actual benchmark code.
5. **Verdict:** The empirical benchmark executed with **$300.0\text{ ms}$ task latency and an $80.0\text{ ms}$ threshold**.

---

## 2. Clarification of "100% Pass Rate" vs "100% Request Completion"

The Master Audit Report noted that all 6 reliability tests passed ($100\%$). However, reviewers questioned whether this implies that all requests were completed successfully.

**Crucial Engineering Distinction:**
A reliability test suite verifies **the correct handling of adverse conditions**. Passing a reliability test means the system exhibited the expected defensive behavior:

| Test ID | Test Name | Injected Adverse Condition | Request Outcome | Why Test Passed |
|---|---|---|---|---|
| **TEST-01** | `worker_crash_and_failover` | Crash on primary worker | **SUCCESS** (via backup) | Worker failover recovered the request |
| **TEST-02** | `execution_and_queue_timeouts` | 300 ms sleep ($> 80\text{ ms}$ SLA) | **TIMEOUT** | Timeout guardrail caught slow request |
| **TEST-03** | `queue_saturation_backpressure` | 10 requests to queue of size 2 | **REJECTED** | Backpressure prevented queue overflow |
| **TEST-04** | `circuit_breaker_tripping_and_recovery` | 3 consecutive worker errors | **TRIPPED & HEALED** | Circuit breaker isolated faulty worker |
| **TEST-05** | `non_idempotent_task_retry_prevention` | Non-idempotent task failure | **FAILED** | Retry suppressed to protect state |
| **TEST-06** | `stale_telemetry_detection` | 10-second old telemetry sample | **STALE FLAGGED** | Outdated host telemetry rejected |

Only TEST-01 resulted in a successfully fulfilled inference request. Tests 02, 03, and 05 resulted in **controlled timeouts, rejections, or safe failures**.
The report of "100% Reliability Pass Rate" refers strictly to **policy conformance and safety enforcement**, not uniform request completion.

### Required Manuscript Corrections
- In Section V of the manuscript, state clearly: "In automated resilience validation across 6 failure scenarios, SETU-NETRA achieved 100% policy enforcement: successfully catching timeouts (300 ms vs 80 ms SLA), suppressing retries on non-idempotent operations, raising backpressure under queue saturation, and isolating crashing workers via circuit breaking."
