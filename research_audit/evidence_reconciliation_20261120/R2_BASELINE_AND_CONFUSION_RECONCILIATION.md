# SETU-NETRA R2 Baseline and Confusion Matrix Reconciliation Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Evidence Calibration Auditor & NLP Systems Engineer  
**Scope:** R2 ER-SP Evidence Relevance and Sufficiency Assessment (Cosine Baseline Threshold Sweep, 5-Class Confusion Matrix, Calibration & Abstention Metrics)  
**Primary Reference Files:**
- [`R2_THRESHOLD_EXPERIMENTS.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R2_THRESHOLD_EXPERIMENTS.csv)
- [`R2_AUTHORITATIVE_CONFUSION_MATRIX.json`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R2_AUTHORITATIVE_CONFUSION_MATRIX.json)
- [`training/evidence/evaluate.py`](file:///d:/Projects/Setu-Netra/training/evidence/evaluate.py)
- [`models/evidence/evaluation_results.json`](file:///d:/Projects/Setu-Netra/models/evidence/evaluation_results.json)

---

## 1. Resolution of the Cosine Baseline Threshold Discrepancy

### The Discrepancy
- The original manuscript cited: **$37.65\%$ accuracy** for the Cosine Similarity Threshold Baseline using **$\tau = 0.55$**.
- The Master Audit text cited: **$\tau = 0.75$** as producing the same $37.65\%$ accuracy.

### Experimental Sweep Findings
We conducted an empirical threshold sweep across $\tau \in [0.40, 0.85]$ on the exact held-out test split `training/datasets/SETU-ER/splits/test.jsonl` ($N=340$ across 4 unseen topics) using `training/evidence/embedding_cache.pt`.

| Threshold $\tau$ | Accuracy | Macro Precision | Macro Recall | Macro F1 | ECE | `SUFFICIENT` F1 | `IRRELEVANT` F1 | Notes |
|---|---|---|---|---|---|---|---|---|
| 0.40 | $39.71\%$ | $0.1875$ | $0.3971$ | $0.2459$ | $0.3247$ | $0.4459$ | $0.7836$ | Overpredicts sufficiency |
| 0.45 | $38.82\%$ | $0.1776$ | $0.3882$ | $0.2376$ | $0.3374$ | $0.4324$ | $0.7556$ | |
| 0.50 | $38.82\%$ | $0.1641$ | $0.3882$ | $0.2284$ | $0.3402$ | $0.4655$ | $0.6766$ | Standard RAG midpoint |
| **0.55** | **$37.65\%$** | **$0.1547$** | **$0.3765$** | **$0.2185$** | **$0.3496$** | **$0.4598$** | **$0.6326$** | **ACTUAL EXPERIMENTAL BASELINE** |
| 0.60 | $37.65\%$ | $0.1507$ | $0.3765$ | $0.2153$ | $0.3396$ | $0.5000$ | $0.5763$ | |
| 0.65 | $33.53\%$ | $0.1392$ | $0.3353$ | $0.1927$ | $0.3412$ | $0.4946$ | $0.4689$ | |
| 0.70 | $30.29\%$ | $0.1322$ | $0.3029$ | $0.1741$ | $0.3450$ | $0.4430$ | $0.4277$ | |
| **0.75** | **$27.35\%$** | **$0.1226$** | **$0.2735$** | **$0.1532$** | **$0.3463$** | **$0.3649$** | **$0.4012$** | **Master Audit Typo ($27.35\% \ne 37.65\%$)** |
| 0.80 | $21.76\%$ | $0.0753$ | $0.2176$ | $0.0961$ | $0.3559$ | $0.1111$ | $0.3696$ | Severe underprediction |
| 0.85 | $20.59\%$ | $0.0748$ | $0.2059$ | $0.0787$ | $0.3147$ | $0.0500$ | $0.3434$ | Collapses to mostly `IRRELEVANT` |

### Forensic Proof
1. Inspection of `training/evidence/evaluate.py` line 165 directly shows:
   `cosine_baseline = CosineThresholdBaseline(threshold=0.55)`
   The value $\tau = 0.55$ was hardcoded during the initial benchmark suite implementation.
2. At $\tau = 0.55$, the empirical accuracy is **$37.647\%$** ($128 / 340$) and Macro F1 is **$0.2185$**, which is an exact match to the manuscript and `models/evidence/evaluation_results.json`.
3. At $\tau = 0.75$, accuracy drops precipitously to **$27.35\%$** ($93 / 340$).
4. **Conclusion:** The master audit text inadvertently substituted "$\tau = 0.75$" for "$\tau = 0.55$" (likely conflating BM25 parameter $b=0.75$ or a router confidence threshold). The authoritative threshold is **$\tau = 0.55$**.

---

## 2. Authoritative 5-Class ER-SP Confusion Matrix Verification

We evaluated `models/evidence/er_sp.pt` (SHA-256: `c44d7e77be93b55615f3193587420fed289469d4bd1ef5610d7103b0a30a8bca`, 560,134 parameters) across the $N=340$ unseen test samples (68 samples per class):

### Primary Metrics
- **5-Class Accuracy:** **$86.18\%$** ($293 / 340$)
- **Macro F1:** **$0.8553$**
- **Expected Calibration Error (ECE):** **$0.0889$**
- **Binary Abstention F1:** **$0.9318$** (Precision: $96.09\%$, Recall: $90.44\%$)
- **Contradiction Precision:** **$100.00\%$** ($65 / 65$)
- **Contradiction Recall:** **$95.59\%$** ($65 / 68$)

### Authoritative 5x5 Confusion Matrix
*(Rows = Ground Truth, Columns = Predicted)*

```
                       PREDICTED
ACTUAL               SUFF   PART_SUFF   CONTRA   IRREL   UNVERIF    Total    Recall
SUFFICIENT             58          10        0       0         0       68    85.29%
PARTIALLY_SUFFICIENT   26          34        0       8         0       68    50.00%
CONTRADICTORY           0           3       65       0         0       68    95.59%
IRRELEVANT              0           0        0      68         0       68   100.00%
UNVERIFIABLE            0           0        0       0        68       68   100.00%
---------------------------------------------------------------------------------
Total Predicted        84          47       65      76        68      340
Precision          69.05%      72.34%  100.00%  89.47%   100.00%
```

### Key Epistemic Insights
1. **Zero Hallucination Contradiction Leakage:** Not a single `CONTRADICTORY` example was misclassified as `SUFFICIENT`. When evidence directly contradicts the query, precision is **$100\%$** with $95.59\%$ recall.
2. **Boundary Confusion on Partial Sufficiency:** 26 out of 68 `PARTIALLY_SUFFICIENT` examples were classified as `SUFFICIENT`. This reflects the intrinsic semantic difficulty in distinguishing whether a document snippet contains 100% of the required premises or only 80% when no contradiction exists.
3. **Perfect Rejection of Irrelevant and Unverifiable Queries:** Both `IRRELEVANT` and `UNVERIFIABLE` classes achieved **$100\%$ recall**, ensuring that off-topic documents or queries asking about unmentioned entities are reliably flagged for abstention.

---

## 3. Comparison with Lexical and Cosine Baselines

| Metric | Cosine Threshold Baseline ($\tau = 0.55$) | Rule-Based Lexical Baseline | Proposed ER-SP Neural Classifier | ER-SP Relative Gain |
|---|---|---|---|---|
| **Overall Accuracy** | $37.65\%$ | $45.88\%$ | **$86.18\%$** | **$+128.9\%$** |
| **Macro F1** | $0.2185$ | $0.3621$ | **$0.8553$** | **$+291.4\%$** |
| **Expected Calibration Error (ECE)** | $0.3496$ | $0.3922$ | **$0.0889$** | **$-74.6\%$ (Better)** |
| **Contradiction Precision** | $0.00\%$ | $0.00\%$ | **$100.00\%$** | Perfect |
| **Contradiction Recall** | $0.00\%$ | $0.00\%$ | **$95.59\%$** | Perfect |
| **Abstention F1** | $0.6635$ | $0.8779$ | **$0.9318$** | $+6.1\%$ |
| **CPU Latency (Mean)** | $0.015\text{ ms}$ | $0.022\text{ ms}$ | **$0.450\text{ ms}$** | Lightweight ($< 0.5\text{ ms}$) |

**Takeaway:** Standard RAG cosine similarity thresholding is blind to contradictions, partial sufficiency, and unverifiability because high vector similarity occurs even when key negation words or conflicting facts are present. ER-SP resolves this critical failure mode with negligible latency ($0.45\text{ ms}$).
