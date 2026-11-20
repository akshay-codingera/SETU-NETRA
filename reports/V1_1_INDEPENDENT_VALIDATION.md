# SETU-NETRA V1.1.0 — INDEPENDENT TECHNICAL VALIDATION & RESEARCH AUDIT REPORT

**Date:** November 11, 2026  
**Auditor:** Principal AI Systems Researcher, Distributed Systems Architect & Reliability Reviewer  
**Target Codebase:** SETU-NETRA V1.1.0 (`HEAD`)  
**Hardware & Environment:** Windows 11 Enterprise (10.0.26200), Intel Core i5-1334U (12 vCPUs), 16.0 GB RAM, Python 3.14.7 (`.venv`), Ollama Daemon 0.34.2 (`http://127.0.0.1:11434`)  
**Verification Scope:** Source Code, Runtime Behavior, Unit & Integration Tests (185/185 Green), Socket Network Interception, Raw Benchmark Data, Multi-Page End-to-End Execution.

---

## 1. EXECUTIVE AUDIT SUMMARY & FORMAL CLAIM VERDICTS

Every technical claim in the SETU-NETRA V1.1.0 release documentation has been independently evaluated against empirical runtime tests, socket tracing, raw telemetry, and statistical data stores. The formal audit classifications are defined as:
- **`VERIFIED`**: Proven by reproducible runtime execution and persisted empirical data.
- **`PARTIALLY VERIFIED`**: Conceptually implemented and operational, but quantitative metrics require scientific recalibration or contextual qualification.
- **`NOT VERIFIED`**: Claimed capability is simulated, unconfigured, or lacks empirical execution proof.
- **`FAILED`**: Direct discrepancy between claimed behavior and actual source code/runtime execution.

### Master Claim Classification Matrix

| # | Subsystem / Claim | Claimed in V1.1 Report | Empirical Finding | Audit Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | **Ollama Qwen 3.5 2B Integration** | Local generative model running on consumer CPU | Verified runtime execution: 11.0–15.0 tokens/s, 2.8–16.6s latency | **`VERIFIED`** |
| **C2** | **Think Mode Trace Isolation** | `<think>` tags captured in metadata, clean answer | Captured 1,026-char thinking trace in metadata; stripped from clean response | **`VERIFIED`** |
| **C3** | **Memory Coexistence & Safeguards** | Headroom protection between Ollama & Transformers | Unloads SmolLM2 when RAM < 3GB; rejects execution if RAM < 1GB | **`VERIFIED`** |
| **C4** | **Concurrency Guard** | Global concurrency serialized to 1 active request | `threading.Semaphore(1)` enforces strictly serialized CPU execution | **`VERIFIED`** |
| **C5** | **Cloud Model Verification** | Gemini, Groq, OpenRouter live inference verified | No API credentials configured in environment; 0 live network calls | **`NOT VERIFIED`** (`NOT_CONFIGURED`) |
| **C6** | **Credential Security** | Zero secret keys leaked in codebase or API | 0 leaks in source code; masking active in settings view (`AIza****`) | **`VERIFIED`** |
| **C7** | **Zero-Egress Local-Only Mode** | Complete network isolation under Local-Only | 0 external sockets opened; `PermissionError` stops cloud adapters before I/O | **`VERIFIED`** |
| **C8** | **Non-Loopback Host Rejection** | Prohibit remote Ollama hosts under Local-Only | `http://192.168.1.150:11434` immediately rejected with `REJECTED` | **`VERIFIED`** |
| **C9** | **Grounded Extractive 10,000 req/s** | 10,000 req/s AI model inference | In-memory lexical substring slicing (0.05 ms); NOT generative AI | **`PARTIALLY VERIFIED`** (Demarcated) |
| **C10**| **QA Accuracy (EM=0.88, F1=0.915)** | Claimed 88% EM, 91.5% F1 on 100 queries | Raw string EM is 0.000 due to citation tags; Token F1 is 0.2122 | **`FAILED`** (Recalibrated) |
| **C11**| **Retrieval Recall@3 (0.941)** | Recall@3 is 0.941 bounded in [0.0, 1.0] | Verified 0.940 across 100 benchmark queries with nDCG@3 of 0.8981 | **`VERIFIED`** |
| **C12**| **Decoupled 2-Tier Architecture** | Dynamic routing decoupled from worker scheduling | Independent `AdaptiveModelRouter` + 6 switchable scheduling algorithms | **`VERIFIED`** |
| **C13**| **Test Suite Green** | 100% test pass rate | 185 of 185 unit and integration tests passing | **`VERIFIED`** |

---

## 2. PRIORITY 1 — LOCAL MODEL INTEGRATION AUDIT

### 2.1 Empirical Execution Telemetry (Qwen 3.5 2B on CPU)

Independent runtime validation was conducted using `tests/audit_priority1_local_model.py` connecting directly to Ollama daemon 0.34.2 hosting `qwen3.5:2b` (Q8_0 quantization, 1.9B parameters, 2,048-token context window).

```json
{
  "qwen_direct_no_think": {
    "status": "SUCCESS",
    "execution_time_ms": 5080.82,
    "wall_clock_elapsed_ms": 5081.1,
    "prompt_tokens": 25,
    "completion_tokens": 59,
    "tokens_per_second": 13.49,
    "result_preview": "An Operating System page table is a data structure that maps virtual memory addresses to physical memory addresses...",
    "thinking_in_metadata": false
  },
  "qwen_direct_with_think": {
    "status": "SUCCESS",
    "execution_latency_ms": 23464.79,
    "prompt_tokens": 25,
    "completion_tokens": 258,
    "tokens_per_second": 11.01,
    "thinking_trace_length_chars": 1026,
    "clean_result_preview": "[Reasoning Summary: Thinking Process: Mutex vs Spinlock analysis...]"
  },
  "pipeline_end_to_end": {
    "status": "SUCCESS",
    "model_id": "ollama/qwen3.5:2b",
    "executing_worker": "ollama/qwen3.5:2b_w1",
    "execution_latency_ms": 14944.62,
    "active_scheduler": "AdaptiveResilientScheduler",
    "tokens_per_second": 13.86
  }
}
```

### 2.2 Thinking Mode Trace Isolation
- **Mechanism:** Qwen 3.5 generates reasoning traces between `<think>` and `</think>` tags.
- **Verification:** `OllamaProviderAdapter._strip_thinking_tags()` strips the tag envelope and captures the raw chain-of-thought into `metadata["thinking"]`.
- **Verdict:** Clean final answers are delivered to downstream conversational interfaces without polluting the dialogue with intermediate scratchpad tokens.

### 2.3 Memory Coexistence & Safeguards
- **Coexistence Invariant:** Ollama Qwen 3.5 2B (Q8_0, ~2.0 GB RAM) and PyTorch SmolLM2-135M (~270 MB RAM) must not exhaust consumer RAM.
- **Defect Identified & Corrected:** In `_validate_memory_and_coexistence()`, the `< 1000 MB` critical check originally preceded the `< 3000 MB` coexistence check. When RAM dropped below 1000 MB, it exited with an error *before* unloading SmolLM2. The evaluation order was fixed so SmolLM2 is unloaded first, telemetry is refreshed, and the 1000 MB floor is evaluated subsequently.
- **Verification:** When host available RAM drops below 1000 MB, requests are rejected in 2.1 ms with `Status: REJECTED` (`"Critically low host RAM"`), preventing system freezing or host out-of-memory crashes.

---

## 3. PRIORITY 2 — CLOUD PROVIDER RUNTIME VALIDATION

### 3.1 Live Inference Status Categorization

A source code and credential audit was conducted across all cloud adapter classes (`GeminiCloudAdapter`, `GroqCloudAdapter`, `OpenRouterCloudAdapter`):

| Provider | Adapter Class | Status Reported by Adapter | Live API Execution | Final Scientific Classification |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `GeminiCloudAdapter` | `NOT_CONFIGURED` | None (0 requests) | **`NOT_CONFIGURED`** |
| **Groq Cloud** | `GroqCloudAdapter` | `NOT_CONFIGURED` | None (0 requests) | **`NOT_CONFIGURED`** |
| **OpenRouter** | `OpenRouterCloudAdapter` | `NOT_CONFIGURED` | None (0 requests) | **`NOT_CONFIGURED`** |

> [!IMPORTANT]
> The SETU-NETRA codebase contains full, type-safe REST adapters for Gemini, Groq, and OpenRouter with exponential backoff and payload serialization. However, **no live inference has been conducted against cloud endpoints** due to unconfigured API keys. Claims in demonstration materials must explicitly state that cloud providers are in a verified `NOT_CONFIGURED` standby state.

### 3.2 Credential Protection Audit
- **Source Code Scan:** Zero hardcoded API keys, tokens, or plaintext credentials exist in the git repository.
- **UI Placeholders:** Generic HTML placeholder strings (`AIzaSy...`, `gsk_...`) in `src/setu_netra/ui/app.py` were replaced with descriptive labels (`Enter Gemini API key...`) to eliminate static analysis false alarms.
- **In-Memory Masking:** All credentials retrieved through `get_system_settings_view()` are strictly masked (`AIza****2345`).

---

## 4. PRIORITY 3 — SECURITY & ZERO-EGRESS VALIDATION

### 4.1 Local-Only Socket Interception Audit
Outbound network calls were monitored using runtime socket interception (`socket.socket.connect` monkeypatching) across 5 rigorous attack vectors:
1. **Cloud Adapter Invocation:** Direct execution of `GeminiCloudAdapter`, `GroqCloudAdapter`, and `OpenRouterCloudAdapter` under `is_local_only() == True` raised `PermissionError` immediately.
2. **Socket Verification:** Exactly **0 external socket connections** were initiated.
3. **Remote Daemon Rejection:** Configuring `OllamaProviderAdapter` with a non-loopback address (`http://192.168.1.150:11434`) was blocked and returned `Status: REJECTED`.

### 4.2 Web API Defensive Boundaries
- **50MB Upload Ceiling:** `POST /api/upload` inspects `Content-Length` before buffer allocation and returns `HTTP 413 Payload Too Large` if exceeding 50 MB.
- **Path Traversal Sanitization:** Malicious filenames (`../../malicious_payload.pdf`) are sanitized with `Path(raw_name).name`, confining files strictly to `output/uploads/`.
- **SQL Injection Defense:** SQLite store parameterized queries safely neutralize malicious inputs (`1' OR '1'='1'`, `'; DROP TABLE documents; --`) with zero data leakage or table corruption.

---

## 5. PRIORITY 4 — RESEARCH & BENCHMARK AUDIT

### 5.1 Reconciled KPI Metrics Table

Discrepancies between illustrative presentation cards and persisted empirical benchmark results (`benchmarks/v1_1/data/aggregated_baseline_results.json`) were audited:

| Benchmark Metric | Claimed in Presentation | Empirical Measured Value | Scientific Explanation of Discrepancy |
| :--- | :--- | :--- | :--- |
| **Exact Match (EM)** | `0.880` | **`0.000`** (100 queries) | Extractive answers append citation tags `[Doc: ..., Page: ..., Block: ...]`; character-by-character string matching fails against gold short phrases. |
| **Token F1 Score** | `0.915` | **`0.2122`** (Condition D) | Sentence-level extractive spans dilute token precision against gold concise phrases. |
| **Grounded Citation Precision** | `0.932` | **`0.8200`** (Condition D) | Reaches 82.0% across all 100 queries; 100% on purely factual subset queries. |
| **Retrieval Recall@3** | `0.941` | **`0.9400`** (Condition A-D) | **Empirically verified** across 100 multi-document queries with nDCG@3 of 0.8981. |
| **Mean Reciprocal Rank (MRR)** | Not highlighted | **`0.8767`** | First relevant document passage appears at mean rank 1.14. |
| **End-to-End Latency Speedup** | Qualitative | **`104.6 ms` vs `2593.6 ms`** | Decoupled Adaptive + CAS delivers a **24.8x latency reduction** over Fixed + Round Robin. |

### 5.2 Algorithmic Extraction vs. Neural Inference Throughput

The reported "10,000 requests/sec" metric for `grounded-extractive-qa-v1` was audited:
- **`grounded-extractive-qa-v1`:** Deterministic in-memory substring slicing and regex matching across pre-indexed passage strings. Execution latency is **0.05 ms (50 microseconds)**, yielding 10,000 req/s. It is **NOT** neural generative AI.
- **`all-MiniLM-L6-v2`:** Dense neural sentence transformer bi-encoder (6 layers, 384 dimensions). Throughput: **116.6 req/s (8.57 ms latency)**.
- **`SmolLM2-135M-Instruct`:** Autoregressive causal SLM on CPU. Throughput: **0.83 req/s (1,208 ms latency, 24.8 tokens/s)**.
- **`Qwen 3.5 2B (Ollama)`:** Quantized (Q8_0) 1.9B autoregressive transformer on CPU. Throughput: **0.06–0.35 req/s (2,898–16,661 ms latency, 11.0–15.0 tokens/s)**.

---

## 6. PRIORITY 5 — END-TO-END MULTI-PAGE ACCEPTANCE RESULTS

A 10-step validation test (`tests/audit_priority5_e2e_acceptance.py`) was executed on a real 2-page document (`output/e2e_acceptance_multipage.pdf`). All 10 steps passed:

```mermaid
flowchart LR
    S1[1. Ingestion] --> S2[2. Layout OCR]
    S2 --> S3[3. Question Extraction]
    S3 --> S4[4. Hybrid Retrieval]
    S4 --> S5[5. Negation Check]
    S5 --> S6[6. Spatial Bounds]
    S6 --> S7[7. Extractive QA]
    S7 --> S8[8. Qwen 3.5 Generative]
    S8 --> S9[9. Adaptive Routing]
    S9 --> S10[10. Local-Only 0-Egress]
```

1. **Step 1 (Ingestion):** Ingested 2-page PDF; status `PROCESSED`, 2 pages rasterized via `pypdfium2`.
2. **Step 2 (Layout & OCR):** 8 layout blocks indexed with 4-tuple `(x0, y0, x1, y1)` bounding boxes across pages 1 and 2.
3. **Step 3 (Question Extraction):** Extracted embedded questions candidates matching document contents.
4. **Step 4 (Hybrid Retrieval):** Top retrieved passage correctly matched target architectural description (score 0.9688).
5. **Step 5 (Negation Check):** Retrieved evidence surfaced explicit negation constraint (`"does not bypass"`).
6. **Step 6 (Spatial Bounds):** Citation coordinates mapped to positive page dimensions `(77.0, 200.0, 1100.0, 280.0)`.
7. **Step 7 (Extractive QA):** Grounded answer returned with verified provenance `[Doc: ..., Page: 1, Block: 2]`.
8. **Step 8 (Generative SLM):** Qwen 3.5 2B synthesized a grounded sentence with thinking tags cleanly stripped.
9. **Step 9 (Adaptive Routing):** Router classified factual intent to extractive engine and reasoning to SLM; worker pool remained healthy.
10. **Step 10 (Local-Only Boundary):** 0 outbound external sockets opened; cloud inference safely intercepted.

---

## 7. PRIORITIZED DEFECT LIST & FACULTY DEMO READINESS

### Defects Identified & Status

1. **[RESOLVED] SmolLM2 Coexistence Unload Sequence in `ollama_adapter.py`:**
   - *Issue:* Critical 1000MB RAM check exited before triggering SmolLM2 unload.
   - *Fix:* Re-ordered so SmolLM2 unloads first, freeing ~270MB RAM before floor evaluation.
2. **[RESOLVED] UI Benchmark Cards Misaligned with Raw Stores in `app.py`:**
   - *Issue:* Screen 5 displayed unverified 0.880 EM / 0.915 F1 figures.
   - *Fix:* Reconciled to real empirical metrics: Recall@3 (0.940), nDCG@3 (0.898), Citation Precision (0.820), MRR (0.877).
3. **[RESOLVED] Missing Upload Size & Path Sanitization in `app.py`:**
   - *Issue:* Raw `POST /api/upload` accepted unbounded length and unsanitized filename.
   - *Fix:* Added 50MB ceiling (`HTTP 413`) and `Path(filename).name` sanitization.
4. **[RESOLVED] UI Credential Scanner Placeholders:**
   - *Issue:* `AIzaSy...` strings in HTML inputs triggered false credential alerts.
   - *Fix:* Replaced with generic descriptive placeholders.

### Final Demonstration Verdict

**VERDICT:** **READY FOR FACULTY DEMONSTRATION AND EXTERNAL ACADEMIC EVALUATION**  
- **Unit & Integration Tests:** 185 / 185 Passed (100% green).
- **Security Boundaries:** Verified zero-data-egress under local-only privacy mode.
- **Local AI Execution:** Genuine Qwen 3.5 2B and SmolLM2 SLMs operational on CPU.
- **Empirical Grounding:** Fully reproducible from persisted SQLite and JSON telemetry.
