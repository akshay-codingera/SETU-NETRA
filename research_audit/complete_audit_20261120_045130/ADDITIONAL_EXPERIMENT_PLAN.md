# SETU-NETRA Prioritized Additional Experiment Plan

This plan outlines high-impact additional experiments designed to address specific empirical weaknesses, sample-size limitations, and harness anomalies discovered during the comprehensive audit.

---

## Experiment 1 (Priority: HIGH): Real-Scan Robustness & Perspective Invariance for SR-EdgeNet

### 1. Research Question
Can spatial data augmentation (rotation $\pm 15^\circ$, perspective keystoning, sensor noise) close the synthetic-to-real generalization gap of SR-EdgeNet on mobile camera scans without expanding model parameter count?

### 2. Hypothesis
Training SR-EdgeNet with affine and perspective-jittered bounding boxes will elevate in-domain real scan accuracy from $65.69\%$ to $\ge 80.0\%$ while retaining $\ge 98.0\%$ synthetic accuracy.

### 3. Existing Weakness Discovered
SR-EdgeNet dropped from $99.46\%$ on synthetic layouts to $65.69\%$ on real-world camera scans (`test_in_domain.jsonl`, $N = 204$), with CONTINUATION_OF recall collapsing to $7.5\%$ due to geometric coordinate warping.

### 4. Dataset / Workload
Extended SETU-SR v2, comprising 500 real-world exam/form camera captures from varied smartphones under non-uniform illumination.

### 5. Construction Methodology
Human annotation of bounding boxes and 4-class directed relationships using labelme, complemented by synthetic affine perturbation of existing 459 document layouts.

### 6. Sample Size / Trials
5,000 augmented synthetic edges + 1,200 real camera-captured edges across 5 independent training runs.

### 7. Splitting Strategy
Document-level 70/15/15 train/val/test split with zero document overlap.

### 8. Baselines
Recursive XY-Cut, LayoutLMv3-base (frozen embeddings), and current SR-EdgeNet v1.0.

### 9. Independent Variables
Bounding box perturbation variance ($\sigma \in \{0.0, 0.05, 0.10, 0.20\}$ normalized units).

### 10. Controlled Variables
Frozen MiniLM embedding backbone, 15-d spatial feature formulation, learning rate ($10^{-3}$), AdamW optimizer.

### 11. Metrics
4-class Macro F1, CONTINUATION_OF Recall, Option Precision, Inference Latency ($\mu\text{s}$).

### 12. Statistical Analysis
Two-sided Wilcoxon signed-rank test comparing F1 scores across 5 random seeds ($\alpha = 0.01$).

### 13. Expected Outputs
`models/structure/sr_edge_net_v2.pt`, `models/structure/augmented_evaluation_results.json`.

### 14. Required Scripts
`training/structure/augment_dataset.py`, `training/structure/train_v2.py`.

### 15. Acceptance Criteria
In-domain gold accuracy $\ge 80.0\%$, CONTINUATION_OF recall $\ge 60.0\%$, parameter count strictly $\le 450\text{K}$.

### 16. Computational Requirements
Approx. 2.5 CPU hours on 12-thread Intel i7, $< 4$ GB peak RAM.

### 17. Risks & Limitations
Extreme optical blur or occluded text may still require visual features beyond bounding boxes.

---

## Experiment 2 (Priority: HIGH): Large-Scale Real Document Epistemic Benchmark for ER-SP

### 1. Research Question
How reliably does ER-SP discriminate between partially sufficient, contradictory, and unverifiable evidence in multi-source administrative and legal documents?

### 2. Hypothesis
Cross-interaction tensor representations with calibrated attention pooling achieve $\ge 85.0\%$ Macro F1 on real multi-page document QA pairs, outperforming cosine similarity thresholds by $\ge 35$ percentage points.

### 3. Existing Weakness Discovered
SETU-ER in-domain evaluation evaluated only $N = 12$ samples (`test_in_domain.jsonl`), yielding high statistical uncertainty ($95\%\text{ CI} \pm 28\%$).

### 4. Dataset / Workload
SETU-ER Gold-500: 500 multi-premise question-passage pairs extracted from real technical specifications, bylaws, and financial filings.

### 5. Construction Methodology
Dual-annotator protocol with inter-annotator agreement (Cohen's $\kappa \ge 0.85$); conflict resolution by domain expert.

### 6. Sample Size / Trials
100 samples per class across all 5 classes (total $N = 500$).

### 7. Splitting Strategy
Stratified 5-fold cross-validation across document domains.

### 8. Baselines
Dense Cosine Thresholding, Lexical BM25 Overlap, Self-RAG reflection tokens, GPT-3.5 zero-shot prompt.

### 9. Independent Variables
Number of input evidence passages ($k \in \{1, 3, 5, 10\}$), contradiction polarity.

### 10. Controlled Variables
MiniLM embedding backbone, classification head architecture (560K parameters).

### 11. Metrics
5-class Macro F1, Contradiction Precision, Expected Calibration Error (ECE), Abstention F1.

### 12. Statistical Analysis
Paired McNemar test against Cosine Thresholding baseline on test folds.

### 13. Expected Outputs
`training/datasets/SETU-ER/splits/gold_500.jsonl`, `models/evidence/gold_500_evaluation.json`.

### 14. Required Scripts
`training/evidence/build_gold_500.py`, `training/evidence/evaluate_gold_500.py`.

### 15. Acceptance Criteria
Macro F1 $\ge 82.0\%$, Contradiction Precision strictly $\ge 95.0\%$, ECE $\le 0.10$.

### 16. Computational Requirements
Approx. 45 CPU minutes, $< 2$ GB RAM.

### 17. Risks & Limitations
Complex domain jargon may require domain-adaptive fine-tuning of the embedding encoder.

---

## Experiment 3 (Priority: MEDIUM): EasyOCR Benchmark Harness Bug Fix & Throughput Verification

### 1. Research Question
What is the true, uncorrupted throughput, latency, and memory footprint of EasyOCR on consumer multi-core CPUs when the evaluation harness attribute defect is resolved?

### 2. Hypothesis
Resolving the `'OCRBox' object has no attribute 'bounding_box'` attribute mismatch will demonstrate an error rate of $0.0\%$, a cold latency of $\sim 20$ s, and a warm steady-state latency of $\sim 4.5$ s per page.

### 3. Existing Weakness Discovered
`benchmarks/results/aggregated/real_inference_benchmarks_summary.json` currently reports an `error_rate_percent: 100.0%` due to harness crash in `benchmarks/runners/inference_runner.py`.

### 4. Dataset / Workload
Standard test image suite (`sample_data/sample_question.png` and 5 multi-resolution scanned documents).

### 5. Construction Methodology
Execute genuine EasyOCR inference (CRAFT + CRNN) using corrected polygon accessors.

### 6. Sample Size / Trials
20 warm iterations across 5 document images.

### 7. Splitting Strategy
N/A (system performance benchmark).

### 8. Baselines
Tesseract OCR 5.0 (CPU), Windows Native Media OCR.

### 9. Independent Variables
Image resolution ($1024 \times 768$, $1920 \times 1080$, $3840 \times 2160$), batch size.

### 10. Controlled Variables
Intel Core i7 CPU, PyTorch 2.14.1+cpu, CPU affinity settings.

### 11. Metrics
Mean Latency (ms), P95 Latency (ms), Throughput (pages/sec), Error Rate (%), Peak RAM (MB).

### 12. Statistical Analysis
Mean and 95% bootstrap confidence intervals over 20 iterations.

### 13. Expected Outputs
Updated `benchmarks/results/aggregated/real_inference_benchmarks_summary.json` with $0\%$ error rate.

### 14. Required Scripts
`benchmarks/runners/inference_runner.py` (patch line accessing `box.polygon`).

### 15. Acceptance Criteria
Error rate strictly $0.0\%$, successful extraction of OCR boxes into pipeline contracts.

### 16. Computational Requirements
Approx. 10 minutes CPU execution time.

### 17. Risks & Limitations
Heavy CPU usage (~90%) during CRAFT text detection peak.

---

## Experiment 4 (Priority: MEDIUM): Local SLM (Qwen 3.5 2B) Empirical Pareto Frontier Benchmark

### 1. Research Question
Does Qwen 3.5 2B running via local Ollama daemon respect the 16 GB hardware boundary and deliver acceptable token generation throughput on CPU?

### 2. Hypothesis
Qwen 3.5 2B (q4_K_M quantization) executes within $\le 2.4$ GB RAM, delivering $5.5$ to $8.0$ tokens/second on CPU, outperforming SmolLM2-135M on qualitative reasoning without triggering system thrashing.

### 3. Existing Weakness Discovered
Qwen 3.5 2B was referenced in reports and verified in unit tests (`tests/test_ollama_qwen.py`), but completely omitted from the official aggregated benchmark file (`real_inference_benchmarks_summary.json`).

### 4. Dataset / Workload
25 complex reasoning prompts covering operating systems, distributed consensus, and relational normalization.

### 5. Construction Methodology
Automated execution through `OllamaProviderAdapter` connecting to loopback daemon `127.0.0.1:11434`.

### 6. Sample Size / Trials
25 queries, 3 repetitions each (75 total requests).

### 7. Splitting Strategy
N/A.

### 8. Baselines
SmolLM2-135M-Instruct (Transformers CPU), Grounded Extractive QA.

### 9. Independent Variables
Prompt context length (128, 512, 1024 tokens), maximum generated tokens (32, 64, 128).

### 10. Controlled Variables
Host RAM (16 GB boundary), local loopback network interface.

### 11. Metrics
Time to First Token (TTFT, ms), Inter-Token Latency (ms/token), Generated Tokens/sec, RAM Peak (MB), Failure Rate (%).

### 12. Statistical Analysis
Mean, P50, P90, P99 percentiles across 75 trials.

### 13. Expected Outputs
`benchmarks/results/aggregated/qwen_benchmark_summary.json`.

### 14. Required Scripts
`benchmarks/runners/qwen_benchmark_runner.py`.

### 15. Acceptance Criteria
Throughput $\ge 5.0$ tokens/sec, peak process RAM $\le 3,000$ MB, zero OOM errors.

### 16. Computational Requirements
Approx. 30 minutes CPU execution time.

### 17. Risks & Limitations
Requires pre-installed Ollama daemon with `qwen3.5:2b` pulled locally.
