# SETU-NETRA Unsupported Figure and Benchmark Claims Audit Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Scientific Reviewer & Reproducibility Auditor  
**Scope:** Figures, Statistical Assertions, and Benchmark Claims Requiring Exclusion or Caveats in Final IEEE Submission  
**Primary Reference Files:**
- [`COMPLETE_FIGURE_SOURCE_RECONCILIATION.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/COMPLETE_FIGURE_SOURCE_RECONCILIATION.csv)
- [`CORRECTED_FIGURE_DATA/`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/CORRECTED_FIGURE_DATA/)
- [`benchmarks/generate_charts.py`](file:///d:/Projects/Setu-Netra/benchmarks/generate_charts.py)
- [`benchmarks/v1_1/data/aggregated_baseline_results.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/data/aggregated_baseline_results.json)

---

## 1. Executive Summary of Unsupported or Overstated Visual Claims

To ensure compliance with strict peer-review standards for IEEE transactions and conferences, we have subjected every project figure and chart to source-level verification.
Three critical issues were identified where published figure claims are either **unsupported by raw benchmark data** or **semantically misattributed**:

1. **Qwen 2.5 2B Model Execution Frontier (UNSUPPORTED):**
   - *Claimed:* A continuous Pareto frontier curve showing Qwen 2.5 2B execution latency, throughput, and memory consumption.
   - *Audit Finding:* `real_inference_benchmarks_summary.json` benchmarked `HuggingFaceTB/SmolLM2-135M-Instruct` ($1,208\text{ ms}$, $24.83\text{ tok/s}$), `all-MiniLM-L6-v2`, `offline-semantic-hash-512`, and `grounded-extractive-qa-v1`. Qwen 2.5 2B was **never run in the benchmark harness**. The Qwen data points in the frontier plot are theoretical extrapolations.
   - *Correction:* Remove Qwen 2.5 2B from empirical benchmark plots. Present `SmolLM2-135M` as the verified generative SLM.

2. **Adaptive Resilient Scheduler $1.17\ \mu\text{s}$ Overhead (CONTRADICTED BY CODE BUG):**
   - *Claimed:* ARS achieves sub-microsecond ($1.17\ \mu\text{s}$) dispatch overhead, outperforming even basic Round Robin ($31.53\ \mu\text{s}$).
   - *Audit Finding:* Discovered code instrumentation defect in `benchmarks/runners/scheduler_runner.py` line 175. The timer stopped **before** `scheduler.execute_with_resilience` was invoked, measuring only the Python `isinstance` check!
   - *Correction:* Remove the $1.17\ \mu\text{s}$ claim. Report true CAS overhead ($123.03\ \mu\text{s}$) and highlight ARS for its **100% request survival rate during worker crashes**, not an artificial timer artifact.

3. **"Worker Utilization" Plot Misnomer (SEMANTIC MISLABELING):**
   - *Claimed:* `worker_utilization.png` shows percentage compute utilization across CPU/GPU cores.
   - *Audit Finding:* Inspection of `benchmarks/generate_charts.py` line 220 reveals that the chart simply plots **the raw integer count of requests dispatched to each worker** ($[w.\text{processed\_count}]$). It does not measure CPU core duty cycles.
   - *Correction:* Retitle the chart as **"Worker Request Distribution (Load Balancing)"**.

4. **"Zero Hallucination" Claim from $N=8$ QA Evaluation (STATISTICALLY UNDERPOWERED):**
   - *Claimed:* 100% abstention and 0.0% hallucination rate across document QA.
   - *Audit Finding:* Evaluated on exactly 8 questions (5 supported, 3 unanswerable). While 100% of the 3 unanswerable queries were abstained upon, an $N=8$ sample size cannot statistically support general immunity to hallucination.
   - *Correction:* Frame this strictly as an initial proof-of-concept case study on Raft consensus documents.

---

## 2. Status of the Factorial ANOVA Claim ($F = 231.60, p < 10^{-26}$)

Reviewers questioned whether the repeated-measures ANOVA claim ($F(1, 99) = 231.60, p = 1.14 \times 10^{-27}$) was fabricated or unsupported.

### Audit Verdict: MATHEMATICALLY VERIFIED WITH METHODOLOGICAL CLARIFICATION
1. **Raw Data Preserved:** In `benchmarks/v1_1/data/`, the exact 100 query evaluations across all 4 experimental conditions are preserved:
   - Condition A (`raw_quality_Condition_A.json`): Fixed Model + Round Robin
   - Condition B (`raw_quality_Condition_B.json`): Fixed Model + Capacity-Aware
   - Condition C (`raw_quality_Condition_C.json`): Adaptive Routing + Round Robin
   - Condition D (`raw_quality_Condition_D.json`): Adaptive Routing + Capacity-Aware
2. **Exact Mathematical Result:** In `aggregated_baseline_results.json`, `anova_citation_precision` reports:
   - $N = 100$, $\text{df}_1 = 1$, $\text{df}_2 = 99$
   - Contrast mean: $0.72$ (Citation precision jumped from $0.10$ to $0.82$)
   - $F\text{-statistic} = \mathbf{231.5957}$
   - $p\text{-value} = \mathbf{1.1408 \times 10^{-27}}$
   - $\text{Partial } \eta^2 = \mathbf{0.7005}$
3. **Methodological Clarification:** The massive F-statistic is mathematically real because Condition A/B used fixed SmolLM2-135M (which struggled to output valid citation tags, achieving only 10% precision), while Condition C/D used Adaptive Routing to direct extractive questions to deterministic regex/extractive blocks (achieving 82% precision). The test measured the dramatic impact of **adaptive routing over an unassisted small model**, not an interaction between large models.
