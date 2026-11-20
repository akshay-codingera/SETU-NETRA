# SETU-NETRA R1 Dataset and Metric Reconciliation Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Document Intelligence Architect & Machine Learning Systems Auditor  
**Scope:** R1 SR-EdgeNet Document Structure Understanding (Dataset Splits, Document IDs, Performance Metrics, Confusion Matrices)  
**Primary Reference Files:**
- [`R1_DATASET_ID_AUDIT.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R1_DATASET_ID_AUDIT.csv)
- [`R1_CONFUSION_MATRIX_RECALCULATION.json`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R1_CONFUSION_MATRIX_RECALCULATION.json)
- [`training/datasets/SETU-SR/dataset_manifest.json`](file:///d:/Projects/Setu-Netra/training/datasets/SETU-SR/dataset_manifest.json)
- [`models/structure/evaluation_results.json`](file:///d:/Projects/Setu-Netra/models/structure/evaluation_results.json)

---

## 1. Document Count Reconciliation: 459 vs 470 Resolved

### The Discrepancy
- Earlier draft notes reported: **470 total document units** (349 train + 75 val + 25 test synthetic + 21 in-domain).
- The Master Audit Report and `dataset_manifest.json` report: **459 total documents**.

### Exhaustive Verification
An exhaustive scan of all four split files in `training/datasets/SETU-SR/splits/` confirmed the exact ground-truth distribution:

| Split File | Nominal Target Count | Actual Unique `doc_id`s | Actual Page Count | Edge Records | Source Composition |
|---|---|---|---|---|---|
| `train.jsonl` | 349 | **347** | 387 | 36,346 | 147 FUNSD + 200 Synthetic |
| `val.jsonl` | 75 | **73** | 78 | 6,584 | 48 FUNSD + 25 Synthetic |
| `test_synthetic.jsonl` | 25 | **25** | 30 | 4,423 | 25 Synthetic |
| `test_in_domain.jsonl` | 21 | **14** | 18 | 204 | 14 In-domain Gold (Scanned) |
| **Total** | **470** | **459** | **513** | **47,557** | **195 FUNSD + 250 Synthetic + 14 In-Domain** |

### Proof of the Discrepancy
1. **FUNSD Empty File Exclusion ($-4$ documents):**
   The nominal plan allocated 149 FUNSD training documents and 50 FUNSD validation documents ($149 + 50 = 199$). During dataset construction, 2 training files (`82252119.json`, `82252120.json`) and 2 validation files (`82252135.json`, `82252136.json`) contained no valid annotated entity-linking pairs or readable text bounding boxes, resulting in 0 candidate edges. The parser correctly discarded them, leaving $147 + 48 = 195$ valid FUNSD documents.
2. **Multi-Page Document Grouping ($-7$ documents):**
   The nominal count of 21 in-domain test units referred to individual physical camera-scanned **page images**. In the structured dataset schema, multi-page exams were grouped under their parent `doc_id`s, reducing the 21 physical pages to **14 distinct document entities** (comprising 18 segmented page records and 204 edge pairs).
3. **Exact Mathematical Reconciliation:**
   $$\text{Nominal Units (470)} - 4\ (\text{Empty FUNSD}) - 7\ (\text{Multi-page Merges}) = \mathbf{459\ Unique Documents}$$
   The authoritative document asset count for SETU-SR is therefore **459 unique documents** spanning **47,557 pairwise edges**.

---

## 2. R1 Performance & Confusion Matrix Reconciliation

All metrics were verified by executing predictions using the saved PyTorch checkpoints on `test_synthetic.jsonl` ($N=4,423$ edges) and `test_in_domain.jsonl` ($N=204$ edges).

### A. Synthetic Test Set Performance ($N=4,423$ edges)

| Model Condition | Checkpoint | Accuracy | Macro Precision | Macro Recall | Macro F1 | Status |
|---|---|---|---|---|---|---|
| **Combined SR-EdgeNet** | `sr_edge_net.pt` | **$99.46\%$** | **$0.9846$** | **$0.9977$** | **$0.9909$** | **CONFIRMED** |
| **Synthetic-Only SR-EdgeNet** | `sr_edge_net_synth_only.pt` | **$99.46\%$** | **$0.9846$** | **$0.9977$** | **$0.9909$** | **CONFIRMED** |
| **FUNSD-Only SR-EdgeNet** | `sr_edge_net_funsd_only.pt` | **$59.62\%$** | **$0.2494$** | **$0.4307$** | **$0.3059$** | **CONFIRMED** |

#### Combined / Synth-Only Confusion Matrix (Synthetic Test)
*(Rows = Ground Truth, Columns = Predicted)*
```
                  PARENT_OF   OPTION_OF   CONTINUATION_OF   NONE      Support
PARENT_OF               387           0                 0      0          387
OPTION_OF                 0        1020                 0      0         1020
CONTINUATION_OF           0           0               365      0          365
NONE                      0           0                24   2627         2651
```
- Only 24 true `NONE` edges were mispredicted as `CONTINUATION_OF`. All other classes achieved $100\%$ precision and recall.

#### FUNSD-Only Confusion Matrix (Synthetic Test)
```
                  PARENT_OF   OPTION_OF   CONTINUATION_OF   NONE      Support
PARENT_OF               330           0                 0     57          387
OPTION_OF               383           0                 0    637         1020
CONTINUATION_OF           1           0                 0    364          365
NONE                    344           0                 0   2307         2651
```
- **Key Observation:** Because FUNSD training data has zero instances of `OPTION_OF` or `CONTINUATION_OF`, the FUNSD-only model has $0\%$ recall and $0\%$ precision on those classes, collapsing to $59.62\%$ accuracy.

---

### B. In-Domain Gold Evaluation ($N=204$ edges from real camera scans)

Reviewers noted a discrepancy between two previously reported in-domain confusion matrices: one with **$65.69\%$ accuracy** and one with **$45.10\%$ accuracy**.

Our audit proves that these two matrices correspond to **two distinct models evaluated on the same held-out in-domain dataset**:

| Model Condition | Checkpoint | In-Domain Accuracy | In-Domain Macro F1 | `OPTION_OF` Precision | `OPTION_OF` Recall |
|---|---|---|---|---|---|
| **Synthetic-Only Model** | `sr_edge_net_synth_only.pt` | **$65.69\%$** | **$0.4715$** | **$88.89\%$** | **$66.67\%$** |
| **Combined Model** | `sr_edge_net.pt` | **$45.10\%$** | **$0.3434$** | **$80.00\%$** | **$44.44\%$** |

#### Why Synthetic-Only Outperforms Combined on In-Domain Scans
1. **Domain Mismatch:** In-domain evaluation documents are **academic examination papers** consisting of question headers, numbered multiple-choice options (`OPTION_OF`), and multi-column running prose (`CONTINUATION_OF`).
2. **FUNSD Label Distribution:** FUNSD consists solely of bureaucratic forms (`header_to_question` and `question_to_answer`). It lacks the concept of horizontal option lists.
3. **Negative Transfer / Label Pollution:** Training on FUNSD biased the combined model towards predicting `PARENT_OF` whenever text blocks were vertically aligned. In the Combined in-domain matrix:
   - 41 `NONE` edges were falsely predicted as `PARENT_OF`.
   - 15 `CONTINUATION_OF` edges were falsely predicted as `PARENT_OF`.
   In contrast, `sr_edge_net_synth_only.pt` preserved clean decision boundaries for horizontal option layouts, achieving **$88.89\%$ precision on `OPTION_OF`** ($24 / 27$) versus $80.00\%$ ($16 / 20$) for Combined.

---

## 3. Structural Metrics vs Reading Order Metrics

To ensure scientific integrity in the manuscript, the following two distinct metrics must **never be conflated**:
1. **Reading-Order Accuracy & Kendall's Tau:**
   - Evaluates 1D sequence sorting of text tokens (XY-Cut baseline achieves $\tau = 1.0$ on clean synthetic documents).
2. **Pairwise Spatial-Relational Edge Classification (SR-EdgeNet):**
   - Evaluates 2D directed semantic edge prediction over the 4-class space (`PARENT_OF`, `OPTION_OF`, `CONTINUATION_OF`, `NONE`).
   - Achieves $99.46\%$ on synthetic test and $65.69\%$ on real-world camera scans.

### Manuscript Action Items
- Replace all references to "470 documents" with **459 documents (47,557 edges)**.
- Report both the Synthetic-Only in-domain result ($65.69\%$ acc, $0.4715$ F1, $88.89\%$ option precision) and the Combined result ($45.10\%$ acc, $0.3434$ F1), explicitly discussing negative transfer from administrative forms to examination layouts.
