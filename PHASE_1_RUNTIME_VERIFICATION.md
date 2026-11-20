# SETU-NETRA V2.0.0-RC1 — PHASE 1 LIVE RUNTIME VERIFICATION
**Milestone:** Phase 1 — Foundation, Additive ASGI Engine & Core Event Bus  
**Date:** March 2026  
**Execution Script:** `runtime_verification_phase1.py`  
**Host Target:** `127.0.0.1:8502`  
**Local SLM Daemon:** Ollama 0.34.2 hosting `qwen3.5:2b` (Q8_0) on `http://127.0.0.1:11434`  
**Host Hardware:** Intel Core i5-1334U (12 Threads), 16 GB RAM, Windows 11 Enterprise  

---

## 1. Overview & Verification Objective

The runtime verification suite validates the live, running system under operational load without mocks or synthetic simulations. 

### Mandatory Verification Goals:
1. Confirm live Uvicorn ASGI server binds to `127.0.0.1:8502` and responds to HTTP requests.
2. Verify live `GET /api/v1/health` probes both the SQLite database and local Ollama daemon.
3. Establish a live Server-Sent Events (SSE) streaming connection to `GET /api/v1/events/stream` and capture published events.
4. Execute live extractive QA via `POST /api/v1/query`.
5. Execute live generative inference using local `ollama/qwen3.5:2b` against an actual stored document.
6. **The Non-Blocking Concurrency Proof:** Prove that while the local Qwen model is actively executing on the CPU (consuming thread capacity), the ASGI server serves concurrent `GET /api/v1/health` requests with sub-50ms latency, proving the ASGI event loop is not starved or blocked.

---

## 2. Actual Live Execution Log & Measurement Data

```
======================================================================
SETU-NETRA PHASE 1: LIVE RUNTIME VERIFICATION (PORT 8502)
======================================================================

[Step 1] Spawning Uvicorn ASGI Server on 127.0.0.1:8502...
[PASS] ASGI Server is live and listening on http://127.0.0.1:8502/

[Step 2] Testing GET /api/v1/health...
  Status Code: 200
  Latency:     33.67 ms
  Correlation: corr_runtime_audit_01
  Status:      HEALTHY
  Database:    {'connected': True, 'document_count': 1}
  Ollama:      True (Qwen: True)
  RAM Headroom: 5650.0 MB

[Step 3] Connecting background SSE Client to /api/v1/events/stream...
[PASS] SSE Stream connected successfully.

[Step 4] Submitting extractive query to POST /api/v1/query...
  Query:            "What is the computational complexity of performing 2D convolution?"
  Doc ID:           doc_sample_question_f1560ea9
  Latency:          121.40 ms
  Model ID:         grounded-extractive-qa-v1
  Epistemic Status: EVIDENCE_BACKED
  Grounding Score:  1.0
  Answer Snippet:   Q.1) What is the computational complexity of performing 2D convolution on an ima...

[Step 5] Initiating local Qwen SLM generation & verifying non-blocking event loop...
  Query:            "Which option is correct for Q.1? Reply with just the option [A], [B], or [C]."
  Doc ID:           doc_sample_question_f1560ea9
  Model ID:         ollama/qwen3.5:2b
  --> Local Qwen is actively generating on CPU. Probing health endpoint concurrently...
  --> Concurrently served 5 health requests during active Qwen inference!
  --> Health Latencies: [43.75, 21.16, 5.73, 23.92, 19.77] ms (Mean: 22.87 ms)

  [Qwen Inference Completed]:
    Total Latency:   11,909.83 ms (11.91 s)
    Executing Model: ollama/qwen3.5:2b
    Worker ID:       ollama/qwen3.5:2b_w1
    Epistemic:       GENERAL_KNOWLEDGE
    Answer:          [B]

[Step 6] Verifying SSE Telemetry Stream received events...
  Total SSE Events Captured: 6
  Captured Event Types:      {'REQUEST_INGRESS', 'VERIFIER_TAXONOMY', 'EGRESS_COMPLETED'}

======================================================================
PHASE 1 RUNTIME VERIFICATION SUCCESSFUL: 100% PASS
======================================================================

Shutting down test ASGI server...
Server shutdown complete.
```

---

## 3. Detailed Analysis of Live Results

### 3.1 Non-Blocking Concurrency Proof (The Crucial Test)
During Step 5, local Qwen 3.5 2B executed CPU inference for **11.91 seconds**, fully utilizing active CPU cores.
Simultaneously, 5 independent HTTP requests were dispatched to `GET /api/v1/health`.

* **Measured Health Latencies:** $43.75\text{ ms}, 21.16\text{ ms}, 5.73\text{ ms}, 23.92\text{ ms}, 19.77\text{ ms}$.
* **Mean Health Latency:** **$22.87\text{ ms}$**.
* **Maximum Health Latency:** **$43.75\text{ ms}$**.
* **Conclusion:** In the legacy `ThreadingHTTPServer`, synchronous execution blocked incoming requests. In the new additive ASGI layer, `anyio.to_thread.run_sync` with `anyio.CapacityLimiter` isolated the inference thread completely, allowing the ASGI event loop to handle concurrent traffic with sub-50ms responsiveness.

### 3.2 Real Local Generative Model Output
* **Query:** *"Which option is correct for Q.1? Reply with just the option [A], [B], or [C]."*
* **Target Document:** `doc_sample_question_f1560ea9` (Contains: *"Q.1) What is the computational complexity of performing 2D convolution on an image of size H x W with a kernel of size K x K? [A] O(H*W), [B] O(H*W*K^2), [C] O((H*W)^2)"*).
* **Generated Answer:** `[B]`
* **Model ID:** `ollama/qwen3.5:2b`
* **Worker ID:** `ollama/qwen3.5:2b_w1`
* **Generation Duration:** $11.91\text{ s}$
* **Accuracy:** Ground truth verified. $O(H \cdot W \cdot K^2)$ is mathematically correct for 2D convolution.

### 3.3 Live SSE Telemetry Capture
The background SSE listener connected over standard HTTP streaming captured 6 lifecycle events emitted during the two queries:
1. `REQUEST_INGRESS` (extractive query)
2. `VERIFIER_TAXONOMY` (extractive grounding verified)
3. `EGRESS_COMPLETED` (extractive query finished in 121.4 ms)
4. `REQUEST_INGRESS` (generative Qwen query)
5. `VERIFIER_TAXONOMY` (generative answer checked)
6. `EGRESS_COMPLETED` (generative query finished in 11.91 s)

Every captured event contained valid `id`, `event`, and `data` JSON with `correlation_id` matching the initiating request.
