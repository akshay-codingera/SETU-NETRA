# SETU-NETRA Qwen 2.5 2B Inference Evidence Audit Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Local Inference Auditor & LLM Systems Reviewer  
**Scope:** Qwen 2.5 2B SLM Execution, Ollama Daemon Adapter, Unit Test Traces, and Benchmark Omission  
**Primary Reference Files:**
- [`src/setu_netra/routing/adapters/ollama_adapter.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/adapters/ollama_adapter.py)
- [`tests/test_ollama_qwen.py`](file:///d:/Projects/Setu-Netra/tests/test_ollama_qwen.py)
- [`benchmarks/results/aggregated/real_inference_benchmarks_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/real_inference_benchmarks_summary.json)
- [`benchmarks/runners/inference_runner.py`](file:///d:/Projects/Setu-Netra/benchmarks/runners/inference_runner.py)

---

## 1. Audit Objective & Empirical Question

Reviewers asked:
*"Does empirical benchmark evidence exist to support the latency, throughput, and hardware footprint curves plotted for Qwen 2.5 2B in the manuscript and figure assets?"*

---

## 2. Investigation of Implementation vs Benchmark Evidence

### A. Adapter & Unit Test Implementation (Verified Present)
The codebase includes a fully realized adapter for local Ollama SLM execution:
- **Adapter Source:** `src/setu_netra/routing/adapters/ollama_adapter.py`
  - Targets `qwen3.5:2b` / `qwen2.5:2b` via loopback REST API (`http://127.0.0.1:11434`).
  - Enforces Local-Only Privacy Mode (blocks external/WAN endpoints).
  - Implements concurrency semaphore guards and `<think>...</think>` chain-of-thought extraction.
- **Unit Test Suite:** `tests/test_ollama_qwen.py`
  - 8 unit tests pass successfully using mock HTTP fixtures and local loopback detection.

### B. Benchmark Execution Records (Missing / Omitted)
Inspection of the official empirical inference benchmark (`benchmarks/runners/inference_runner.py` and `benchmarks/results/aggregated/real_inference_benchmarks_summary.json`) reveals:
1. **Models Evaluated in Official Benchmark:**
   - `easyocr-craft-crnn` (OCR)
   - `sentence-transformers/all-MiniLM-L6-v2` (Dense Embeddings, $8.57\text{ ms}$)
   - `offline-semantic-hash-512` (Hashing, $0.64\text{ ms}$)
   - `grounded-extractive-qa-v1` (Extractive QA, $0.05\text{ ms}$)
   - `HuggingFaceTB/SmolLM2-135M-Instruct` (Generative SLM, $1,208.14\text{ ms}$, $24.83\text{ tok/s}$)
2. **Absence of Qwen 2.5 2B:**
   - `real_inference_benchmarks_summary.json` contains **zero execution entries for Qwen 2.5 2B**.
   - `inference_runner.py` did not instantiate `OllamaProviderAdapter(model_name="qwen3.5:2b")` during the Stage 6 benchmark execution because the Ollama background daemon was not guaranteed to be running in CI/headless test environments.

---

## 3. Evidence Status and Publication Recommendation

| Claim / Metric | Source File | Empirical Status | Recommendation |
|---|---|---|---|
| **Ollama Adapter Implementation** | `ollama_adapter.py` | **VERIFIED** | Describe in system architecture |
| **Local-Only Privacy Enforcement** | `test_ollama_qwen.py` | **VERIFIED** | Highlight as security contribution |
| **Qwen 2.5 2B Benchmarked Latency Curve** | N/A | **UNSUPPORTED** | **Remove from benchmark charts** |
| **Qwen 2.5 2B Benchmarked Throughput** | N/A | **UNSUPPORTED** | **Remove from benchmark charts** |
| **SmolLM2-135M Benchmarked Latency/Throughput** | `real_inference_benchmarks_summary.json` | **VERIFIED ($24.83\text{ tok/s}$)** | **Retain as primary SLM benchmark** |

### Publication Verdict
In the IEEE manuscript, present `HuggingFaceTB/SmolLM2-135M-Instruct` as the empirically measured generative model ($1,208\text{ ms}$ latency, $24.8\text{ tok/s}$ on CPU). Document Qwen 2.5 2B strictly as a supported pluggable local model backend via the Ollama adapter, excluding unmeasured throughput curves.
