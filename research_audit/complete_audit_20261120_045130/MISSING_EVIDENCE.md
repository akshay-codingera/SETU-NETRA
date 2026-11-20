# SETU-NETRA Research Audit: Missing Evidence and Empirical Gaps

This document identifies all missing empirical records, unverified benchmarks, data collection gaps, and harness anomalies discovered during the comprehensive audit of SETU-NETRA R1–R4.

---

## 1. Qwen 3.5 2B Empirical Benchmark in `real_inference_benchmarks_summary.json`

### What is Missing
An empirical throughput, latency, and memory measurement entry for `ollama/qwen3.5:2b` (or `qwen2.5:1.5b`) within the canonical benchmark artifact:
`benchmarks/results/aggregated/real_inference_benchmarks_summary.json`.

### Which Research Claim Depends on It
- Manuscript Claim: Local SLM action operates within the 16 GB RAM boundary generating 5–8 tokens/second on consumer CPU hardware.
- Architecture Claim: AdaptiveModelRouter dynamically routes complex open-ended generative queries to Ollama-hosted local SLMs.

### Why It Matters
While unit tests (`tests/test_ollama_qwen.py`) verify the `OllamaProviderAdapter` implementation and loopback API connectivity, the official Stage 6 real inference benchmark runner (`benchmarks/runners/inference_runner.py`) only executed SmolLM2-135M, all-MiniLM-L6-v2, Offline Hash, Extractive QA, and EasyOCR. Citing Qwen 3.5 2B performance in reports without raw benchmark records leaves the SLM Pareto frontier unsubstantiated.

### Normal Location
`benchmarks/results/aggregated/real_inference_benchmarks_summary.json` under `metrics["ollama/qwen3.5:2b"]`.

### Exact Evidence Required
A reproducible execution of `inference_runner.py` with an active local Ollama daemon hosting `qwen3.5:2b`, recording cold latency, warm token latency (P50, P90, P99), RAM peak (MB), and generated tokens per second over at least 10 test prompts.

---

## 2. Valid EasyOCR Execution Telemetry in Benchmark Runner

### What is Missing
A valid error-free benchmark measurement of EasyOCR in `benchmarks/results/aggregated/real_inference_benchmarks_summary.json`. The current summary reports an `error_rate_percent: 100.0%`.

### Which Research Claim Depends on It
- End-to-end local document ingestion latency and throughput claims on CPU.
- Real-world OCR feasibility within consumer edge compute budgets.

### Why It Matters
Inspection of `benchmarks/results/raw/real_inference_benchmarks_raw.json` revealed that EasyOCR successfully executed CRAFT and CRNN (taking ~4,497 ms per image), but the benchmark harness crashed with:
`AttributeError: 'OCRBox' object has no attribute 'bounding_box'`.
`OCRBox` in `src/setu_netra/core/contracts.py` defines `polygon`, `xmin`, `ymin`, `xmax`, `ymax`, but not `bounding_box`. This was an evaluation harness defect, not a model failure, but it left the benchmark artifact showing 100% failure.

### Normal Location
`benchmarks/results/aggregated/real_inference_benchmarks_summary.json` under `metrics["easyocr-craft-crnn"].error_rate_percent`.

### Exact Evidence Required
Correction of the harness attribute access to `box.polygon` or `(box.xmin, box.ymin, box.xmax, box.ymax)`, re-running 3 warm iterations on CPU, and recording true OCR throughput with 0% error rate.

---

## 3. Large-Scale Real-World Gold Evaluation for R2 (ER-SP)

### What is Missing
A statistically powered real-world in-domain evaluation set for ER-SP. The current in-domain gold set (`training/datasets/SETU-ER/splits/test_in_domain.jsonl`) contains only $N = 12$ samples.

### Which Research Claim Depends on It
- Generalization of epistemic sufficiency and contradiction prediction from synthetic/academic text to noisy scanned documents and real administrative forms.

### Why It Matters
On $N = 12$ samples, ER-SP achieved 58.33% accuracy (7/12) and Macro F1 of 0.4667, while a naive cosine baseline achieved 66.67% (8/12). A sample of 12 items is statistically underpowered (margin of error exceeds $\pm 28\%$).

### Normal Location
`training/datasets/SETU-ER/splits/test_in_domain.jsonl` and `models/evidence/evaluation_results.json`.

### Exact Evidence Required
At least 100 independently collected and human-annotated real document QA evidence pairs across all five classes (SUFFICIENT, PARTIALLY_SUFFICIENT, CONTRADICTORY, IRRELEVANT, UNVERIFIABLE).

---

## 4. Large-Scale End-to-End Document QA Evaluation

### What is Missing
A comprehensive evaluation of the document QA engine. The current evaluation in `benchmarks/results/aggregated/qa_quality_evaluation_summary.json` evaluated only $N = 8$ questions.

### Which Research Claim Depends on It
- Retrieval ranking metrics: MRR ($0.80$), Precision@1 ($0.60$), Recall@3 ($1.00$).
- End-to-end token F1 ($0.53$) and exact match ($0.38$).
- Unsupported abstention accuracy ($100.0\%$) and zero hallucination rate ($0.0\%$).

### Why It Matters
With $N = 8$ total questions (5 supported, 3 unsupported), the 95% confidence interval for Exact Match spans $[0.00, 0.85]$ and for Token F1 spans $[0.13, 0.93]$. While the 100% abstention on the 3 unsupported questions is promising, $N = 3$ is too small for statistical certainty.

### Normal Location
`benchmarks/results/aggregated/qa_quality_evaluation_summary.json` and `benchmarks/datasets/qa_eval_dataset.json`.

### Exact Evidence Required
A benchmark of $\ge 150$ queries across diverse document layouts, containing balanced supported, partially supported, contradictory, and completely unsupported inquiries.

---

## 5. Independent Open-Domain Evaluation for AdaptiveModelRouter

### What is Missing
An evaluation of `AdaptiveModelRouter` on natural, out-of-distribution queries. The current benchmark in `benchmarks/results/aggregated/routing_evaluation_summary.json` uses $N = 20$ synthetic cases.

### Which Research Claim Depends on It
- 100% routing accuracy across 8 categories.
- 100% unsupported task rejection.
- 100% SLA fallback adherence.

### Why It Matters
All 20 test cases were constructed to strictly mirror the keyword and regex patterns in `AdaptiveModelRouter._classify_task()`. A 100% accuracy on rule-matched test cases tests assertion correctness, but does not validate generalization to paraphrased or ambiguous queries.

### Normal Location
`benchmarks/results/aggregated/routing_evaluation_summary.json`.

### Exact Evidence Required
An independent test set of $\ge 100$ real user prompts evaluated blindly against ground truth labels without regex leakage.

---

## 6. Physical Worker Resource Utilization Time-Series

### What is Missing
A true time-series record of worker CPU and RAM percentage utilization during multi-worker concurrent dispatch.

### Which Research Claim Depends on It
- Load balancing effectiveness and worker starvation avoidance under concurrent workloads.

### Why It Matters
The chart generated at `benchmarks/results/charts/worker_utilization.png` actually plots "Mean Scheduling Dispatch Overhead (Microseconds - us)" rather than worker utilization percentage, due to a function naming misnomer in `benchmarks/generate_charts.py`.

### Normal Location
`benchmarks/results/aggregated/scheduler_microbenchmarks_summary.json` and `benchmarks/results/charts/worker_utilization.png`.

### Exact Evidence Required
A telemetry collector sampling per-worker CPU/RAM percentage every 50 ms during the 1,920 scheduler benchmark requests, plotted as a stacked utilization bar or time-series graph.
