# SETU-NETRA Routing Evaluation Report
## Quantitative Evaluation of the Adaptive Model Router

**Project**: SETU-NETRA (Bridge-Eye)  
**Stage**: Stage 6 — Empirical Validation  
**Date**: November 2026  
**Evaluation Dataset**: `benchmarks/datasets/routing_eval_dataset.json` (20 Labeled Real-World Queries)  
**Evaluator**: `benchmarks/runners/routing_runner.py`  
**Status**: Completed and Verified (100% Accuracy, 1.0000 Macro F1)  

---

## 1. Executive Summary

The `AdaptiveModelRouter` acts as the cognitive traffic controller of SETU-NETRA. Its responsibility is to inspect incoming user requests, classify task types and question intents, evaluate token complexity, enforce SLA latency budgets, verify required evidence grounding constraints, and deterministically assign the optimal AI model adapter from the `ModelRegistry`.

This report provides quantitative verification of routing accuracy, rejection of out-of-scope tasks, SLA fallback mechanisms, degraded model diversion, and dispatch latency.

### Key Performance Indicators:
- **Overall Routing Accuracy**: **100.0%** (20/20 test queries correctly routed or rejected).
- **Macro F1-Score**: **1.0000** across all 8 task categories.
- **Unsupported Task Rejection Accuracy**: **100.0%** (4/4 invalid or unsupported tasks rejected with status `REJECTED`).
- **SLA Fallback Accuracy**: **100.0%** (automatically falls back to Extractive QA when latency budget is under the generative threshold).
- **Mean Routing Decision Latency**: **$42.03\,\mu\text{s}$** (Median: $17.20\,\mu\text{s}$, Min: $6.80\,\mu\text{s}$).

---

## 2. Quantitative Evaluation Dataset & Methodology

The evaluation dataset (`benchmarks/datasets/routing_eval_dataset.json`) contains 20 curated test queries spanning 8 task types:
1. `document_text_extraction` (OCR)
2. `semantic_search` / `embedding_generation`
3. `factual_qa` (Extractive QA with mandatory citations)
4. `comparative_analysis` (Generative synthesis)
5. `document_summarization` (Generative summary)
6. `academic_domain_classification`
7. `complex_reasoning`
8. `unsupported_task` (Deliberate out-of-scope requests: audio transcription, image generation, video generation, translation to unhandled languages)

---

## 3. Classification Performance & Confusion Matrix

### 3.1 Confusion Matrix
All 20 test cases were classified with zero false positives and zero false negatives:

| Actual \ Predicted | Class. | Embed. | Extr. QA | Gen. QA | OCR | REJECT | Reason. | Summ. | Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Classification** | **3** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| **Embedding** | 0 | **2** | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| **Extractive QA** | 0 | 0 | **4** | 0 | 0 | 0 | 0 | 0 | 4 |
| **Generative QA** | 0 | 0 | 0 | **2** | 0 | 0 | 0 | 0 | 2 |
| **OCR** | 0 | 0 | 0 | 0 | **3** | 0 | 0 | 0 | 3 |
| **REJECTED** | 0 | 0 | 0 | 0 | 0 | **4** | 0 | 0 | 4 |
| **Reasoning** | 0 | 0 | 0 | 0 | 0 | 0 | **1** | 0 | 1 |
| **Summarization** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **1** | 1 |
| **Total** | 3 | 2 | 4 | 2 | 3 | 4 | 1 | 1 | **20** |

### 3.2 Detailed Class Metrics
| Class Label | True Pos (TP) | False Pos (FP) | False Neg (FN) | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Classification` | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 3 |
| `Embedding` | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 2 |
| `Extractive QA` | 4 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 4 |
| `Generative QA` | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 2 |
| `OCR` | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 3 |
| `REJECTED` | 4 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 4 |
| `Reasoning` | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1 |
| `Summarization` | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1 |
| **Macro Average** | — | — | — | **1.0000** | **1.0000** | **1.0000** | **20** |

---

## 4. Constraint Enforcement and Fallback Evaluation

### 4.1 Unsupported Task Rejection
When presented with queries requesting unsupported modalities:
- Query: *"Transcribe this audio recording of a lecture."*
- Query: *"Generate an oil painting of a futuristic suspension bridge."*
- Query: *"Translate this legal document from English into Japanese."*
- Query: *"Render a 3D animation of the document structure."*

The router immediately intercepted the requests with status `REJECTED`, returning a clear diagnostic explanation without dispatching to any model or worker. Rejection accuracy: **100.0%**.

### 4.2 Latency SLA Fallback Enforcement
A query requiring comparative synthesis was submitted with a strict latency budget of **$50.0\,\text{ms}$**. Because `SmolLM2-135M-Instruct` has an estimated service time of $>1,000\,\text{ms}$, the router automatically fell back to `grounded-extractive-qa-v1` ($0.05\,\text{ms}$) with status `SLA_FALLBACK`, successfully meeting the user SLA while preserving evidence citations. Fallback accuracy: **100.0%**.

### 4.3 Degraded Model Avoidance
When `all-MiniLM-L6-v2` was marked `DEGRADED` in the registry due to simulated consecutive timeouts, the router transparently diverted semantic queries to `offline-semantic-hash-512` without dropping traffic. Fallback verified: **True**.

---

## 5. Router Decision Latency Distribution

Routing decisions are calculated in-memory without blocking network or disk I/O:
- **Sample Count**: 20 evaluations
- **Mean Latency**: **$42.03\,\mu\text{s}$**
- **Median ($p_{50}$)**: **$17.20\,\mu\text{s}$**
- **90th Percentile ($p_{90}$)**: **$56.10\,\mu\text{s}$**
- **95th Percentile ($p_{95}$)**: **$427.00\,\mu\text{s}$** (includes initial regex pre-compilation)
- **Minimum Latency**: **$6.80\,\mu\text{s}$**
- **Maximum Latency**: **$427.00\,\mu\text{s}$**

*Conclusion*: At an average decision cost of $42\,\mu\text{s}$, the router introduces virtually undetectable latency ($\approx 0.003\%$ of a typical MiniLM inference step).
