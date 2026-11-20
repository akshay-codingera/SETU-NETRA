# SETU-NETRA Local Inference Evidence Reconciliation Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Local Inference Auditor  
**Scope:** Local On-Device AI Models (EasyOCR, MiniLM, Semantic Hash, Extractive QA, SmolLM2, and Qwen 2B)  
**Primary Reference Files:**
- [`EASYOCR_HARNESS_FORENSIC_AUDIT.md`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/EASYOCR_HARNESS_FORENSIC_AUDIT.md)
- [`QWEN_INFERENCE_EVIDENCE.md`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/QWEN_INFERENCE_EVIDENCE.md)
- [`benchmarks/results/aggregated/real_inference_benchmarks_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/real_inference_benchmarks_summary.json)

---

## 1. Authoritative Local Inference Benchmark Summary

All genuine local model benchmarks executed on the Intel Core i5-1334U workstation (Windows 11, PyTorch CPU) are consolidated below:

| Model ID | Functional Category | Cold Load Time | Warm Mean Latency | Throughput | Peak Host RAM | Status |
|---|---|---|---|---|---|---|
| `easyocr-craft-crnn` | Optical Character Recognition | $22,826.0\text{ ms}$ | **$4,497.3\text{ ms}$** | $0.22\text{ pps}$ | $3.60\text{ GB}$ | **VERIFIED (Attribute Defect Resolved)** |
| `all-MiniLM-L6-v2` | Dense Text Embedding | $52,004.6\text{ ms}$ | **$8.57\text{ ms}$** | $116.6\text{ req/s}$ | $3.39\text{ GB}$ | **VERIFIED** |
| `offline-semantic-hash-512` | Lightweight Deduplication | $0.01\text{ ms}$ | **$0.64\text{ ms}$** | $1,554.4\text{ req/s}$ | $3.39\text{ GB}$ | **VERIFIED** |
| `grounded-extractive-qa-v1` | Deterministic Exact Match | $0.01\text{ ms}$ | **$0.05\text{ ms}$** | $10,000.0\text{ req/s}$ | $3.39\text{ GB}$ | **VERIFIED** |
| `SmolLM2-135M-Instruct` | Generative Local SLM | $0.01\text{ ms}$ | **$1,208.1\text{ ms}$** | $24.83\text{ tok/s}$ | $2.96\text{ GB}$ | **VERIFIED** |
| `qwen3.5:2b` (Ollama) | Generative Local SLM | Unmeasured | Unmeasured | Unmeasured | N/A | **UNSUPPORTED (Omitted from Benchmark)** |

### Reconciliation Takeaways
1. **EasyOCR Viability:** EasyOCR runs reliably on consumer laptop CPUs at $4.50\text{ s}$ per page.
2. **Generative SLM Reality:** `SmolLM2-135M` delivers an impressive $24.83\text{ tokens/sec}$ on pure CPU within $< 3.0\text{ GB}$ RAM.
3. **Manuscript Alignment:** Remove any unmeasured Qwen 2.5 2B performance curves from the publication, anchoring all SLM claims to `SmolLM2-135M`.
