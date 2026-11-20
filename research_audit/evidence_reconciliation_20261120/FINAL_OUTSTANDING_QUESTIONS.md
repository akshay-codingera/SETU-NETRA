# SETU-NETRA Final Outstanding Research and Engineering Questions

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Scientific Reviewer & Systems Architect  
**Scope:** Transparent Documentation of Unresolved Questions, Methodological Limitations, and Future Experimental Directions  

---

## 1. Overview

In accordance with Section 16 and Section 19 directives, scientific integrity requires explicit documentation of limitations rather than manufactured explanations.
This document details the genuine outstanding questions and engineering frontiers identified during our comprehensive source-to-claim audit.

---

## 2. Priority Outstanding Questions

### Question 1: Document QA Scale and General Hallucination Bounds
- **Current Evidence:** The Document QA benchmark (`benchmarks/results/aggregated/qa_quality_evaluation_summary.json`) evaluates **8 questions** (5 supported, 3 out-of-domain unanswerable) across 2 documents (`consensus.docx`, `exam_questions.txt`).
- **Outstanding Question:** Does the reported $100\%$ abstention accuracy and $0.0\%$ hallucination rate hold across multi-document corpora spanning hundreds of diverse documents and ambiguous distractor chunks?
- **Scientific Impact:** An $N=8$ sample size provides valuable architectural proof-of-concept, but lacks statistical power to claim general hallucination immunity. A large-scale benchmark (e.g. 500+ multi-hop questions) is required before claiming production hallucination elimination.

### Question 2: Resolving Negative Transfer in Document Structure (SR-EdgeNet)
- **Current Evidence:** On real camera-scanned examination papers (`test_in_domain.jsonl`, $N=204$ edges), the synthetic-only model achieves **$65.69\%$ accuracy** and **$88.89\%$ `OPTION_OF` precision**, while the combined model drops to **$45.10\%$ accuracy** and **$80.00\%$ precision**.
- **Outstanding Question:** How can administrative form layouts (FUNSD) and academic multi-column/MCQ layouts be co-trained without negative transfer?
- **Scientific Impact:** FUNSD lacks multiple-choice structures, biasing the model towards overpredicting vertical parent relationships. Domain-adversarial training, loss re-weighting, or hierarchical track conditioning should be explored.

### Question 3: Empirical Benchmarking of Qwen 2.5 2B on Host Hardware
- **Current Evidence:** The local inference benchmark evaluated `HuggingFaceTB/SmolLM2-135M-Instruct` ($1,208\text{ ms}$, $24.83\text{ tok/s}$), but omitted Qwen 2.5 2B because the Ollama background daemon was not integrated into automated CI execution.
- **Outstanding Question:** What are the exact cold load latency, warm token generation throughput, and peak RAM consumption of Qwen 2.5 2B on the Intel Core i5-1334U workstation under varying quantization levels (e.g. Q4_K_M vs Q8_0)?
- **Scientific Impact:** Until raw benchmark traces are recorded in `real_inference_benchmarks_raw.json`, Qwen performance claims must remain categorized as unsupported extrapolations in the manuscript.

### Question 4: True Algorithmic Overhead of `AdaptiveResilientScheduler`
- **Current Evidence:** Due to a timer placement bug in `benchmarks/runners/scheduler_runner.py` line 175, ARS reported an artificial $1.17\ \mu\text{s}$ overhead (measuring only a Python `isinstance` check).
- **Outstanding Question:** What is the true dispatch latency of ARS when including circuit-breaker health filtering, retry tracking, and fallback evaluation?
- **Scientific Impact:** Re-running the benchmark with corrected instrumentation is expected to place ARS between $140\ \mu\text{s}$ and $160\ \mu\text{s}$, confirming its microsecond scalability while maintaining full resilience.

### Question 5: Neural Entailment vs Lexical Verification
- **Current Evidence:** `CitationVerifier` utilizes lexical token set overlap and regex coordinate matching to verify evidence citations.
- **Outstanding Question:** Can a quantized on-device Natural Language Inference (NLI) model (e.g. MobileBERT-NLI) be integrated into the citation pipeline within a $< 10\text{ ms}$ latency budget to provide true semantic entailment verification?
- **Scientific Impact:** This would elevate the downstream verifier from a structural heuristic to a formal neural entailment engine.
