# SETU-SR Dataset Construction & Provenance Report
## Milestone R1: A Multi-Source, Leakage-Free Dataset for Spatial-Relational Edge Classification (`SR-EdgeNet`)

**Author:** Senior AI Research Scientist & Document Intelligence Specialist  
**Project:** SETU-NETRA (Bridge-Eye)  
**Dataset Name:** `SETU-SR` (Spatial-Relational Edge Dataset)  
**Target Architecture:** `SR-EdgeNet` Multi-Class Relational Edge Classifier  
**Status:** Complete, Formally Validated, Ready for Training  
**Audit Date:** November 2026  

---

## Executive Summary

Following the feasibility audit which confirmed that the existing production database contained only 44 candidate pairs (insufficient for neural training), we constructed the **`SETU-SR`** dataset. `SETU-SR` synthesizes three distinct provenance streams:
1. **Academic Form Ground-Truth (`FUNSD`):** 199 real scanned forms with official entity-linking tuples.
2. **Procedural Examination Engine (`Synthetic`):** 250 varied multi-column examination documents generated using Pillow with mathematical ground-truth bounding boxes and relational edges.
3. **Held-Out In-Domain Benchmark (`In-Domain`):** 16 real project images and 5 key pages from `Track-2 Report.pdf` processed through SETU-NETRA's EasyOCR pipeline, yielding 204 verified real-world relationships reserved exclusively for zero-leakage evaluation.

Across all streams, `SETU-SR` comprises **47,557 validated edge records** with standardized 15-dimensional geometric feature vectors and zero document-level split leakage.

```
+----------------------------------------------------------------------------------------------------+
|                                    SETU-SR CORPUS ARCHITECTURE                                     |
+------------------------------------+----------------------------------+----------------------------+
| SOURCE 1: FUNSD (Academic Ground)  | SOURCE 2: Synthetic MCQ Engine   | SOURCE 3: In-Domain Test   |
| - 199 Real Form Scans              | - 250 Procedural Exam Papers     | - 16 Real Project Images   |
| - 13,179 Directed Edges            | - 300 Rendered Canvas Pages      | - 5 Pages Track-2 Report   |
| - Mapped Header/KV Links           | - 34,174 Directed Edges          | - 204 Real-World Edges     |
| - Strict Form Train/Test Split     | - Single & Double Column Layouts | - HELD-OUT GOLD EVALUATION |
+------------------------------------+----------------------------------+----------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------------------------+
|                               CANONICAL LEAKAGE-FREE SPLITS (47,557 EDGES)                         |
|  - train.jsonl:          36,346 edges (FUNSD Train + Synthetic Train)                              |
|  - val.jsonl:             6,584 edges (FUNSD Test + Synthetic Val)                                 |
|  - test_synthetic.jsonl:  4,423 edges (Synthetic Test Split)                                       |
|  - test_in_domain.jsonl:    204 edges (Held-Out In-Domain Gold Benchmark)                         |
+----------------------------------------------------------------------------------------------------+
```

---

## 1. Actual Number of FUNSD Documents Processed

* **Official Source:** Guillaume Jaume et al., *FUNSD: Form Understanding in Noisy Scanned Documents* (ICDAR-W 2019).
* **Archive Size:** 16,838,830 bytes (~16.8 MB uncompressed).
* **Total Documents Processed:** **199 forms**
  * **Training Split:** **149 forms** (located at `training/datasets/SETU-SR/FUNSD/raw/dataset/training_data/`)
  * **Testing Split:** **50 forms** (located at `training/datasets/SETU-SR/FUNSD/raw/dataset/testing_data/`)
* **Total Entities Extracted:** 9,743 entities (7,411 train + 2,332 test).
* **Total Directed Edge Records:** **13,179 edges**
  * `funsd_edges_train.jsonl`: 10,534 edges (4,229 `PARENT_OF`, 6,305 `NONE`)
  * `funsd_edges_test.jsonl`: 2,645 edges (1,064 `PARENT_OF`, 1,581 `NONE`)

---

## 2. Actual Synthetic Documents Generated

* **Generator Module:** `training/structure/synthetic_mcq_generator.py`
* **Random Seed:** Deterministic base seed `42` (`doc_seed = 42 + doc_idx * 17`).
* **Total Documents Generated:** **250 documents**
  * **Single-Column Documents:** 150 documents (`synth_0001` through `synth_0150`)
  * **Double-Column Documents:** 100 documents (`synth_0151` through `synth_0250`)
  * **Multi-Page Continuation:** 50 documents span 2 pages (`synth_0005`, `synth_0010`, etc.).
* **Total Rendered Canvas Images:** **300 PNG images** ($1200 \times 1600\,\text{px}$) saved in `training/datasets/SETU-SR/synthetic/images/`.
* **Total Ground-Truth Annotation JSONs:** **300 JSON files** saved in `training/datasets/SETU-SR/synthetic/annotations/`.
* **Total Synthetic Directed Edges:** **34,174 edges** saved in `training/datasets/SETU-SR/synthetic/synthetic_edges.jsonl`.

---

## 3. Actual In-Domain Documents Processed

The in-domain pipeline extracted actual OCR bounding boxes from the repository's real document assets using `EasyOCREngine` and `DocumentStructureReconstructor`:

```
+----------------------------------------------------------------------------------------------------+
|                                    IN-DOMAIN REAL ASSETS PROCESSED                                 |
+----------------------------+---------------------------------------------------------+-------------+
| Asset Identifier           | Source File Location                                    | OCR Boxes   |
+----------------------------+---------------------------------------------------------+-------------+
| `sample_question_1`        | `sample_data/sample_question.png`                       | 13 boxes    |
| `sample_question_2`        | `sample_data/sample_question2.jpeg`                     | 9 boxes     |
| `sample_question_3`        | `sample_data/sample_question3.jpeg`                     | 20 boxes    |
| `sample_question_4`        | `sample_data/sample_question4.jpeg`                     | 15 boxes    |
| `quest_06`                 | `output/uploads/462cfeeb/quest6.png`                    | 18 boxes    |
| `quest_07`                 | `output/uploads/3a7222f6/quest7.png`                    | 78 boxes    |
| `quest_08`                 | `output/uploads/47b6860b/quest8.png`                    | 49 boxes    |
| `quest_09`                 | `output/uploads/437abd06/quest9.png`                    | 25 boxes    |
| `quest_10`                 | `output/uploads/997f52e3/quest10.png`                   | 14 boxes    |
| `quest_11`                 | `output/uploads/0e23dd66/quest11.png`                   | 26 boxes    |
| `scenario_03_sql`          | `tests/fixtures/image_pipeline/scenario_03_printed_sql` | 9 boxes     |
| `scenario_04_portrait`     | `tests/fixtures/image_pipeline/scenario_04_portrait.png`| 7 boxes     |
| `scenario_06_highres`      | `tests/fixtures/image_pipeline/scenario_06_high_res.png` | 12 boxes    |
| `scenario_07_lowres`       | `tests/fixtures/image_pipeline/scenario_07_low_res.png`  | 5 boxes     |
| `scenario_08_rotated`      | `tests/fixtures/image_pipeline/scenario_08_rotated.jpg`  | 10 boxes    |
| `scenario_09_multiregion`  | `tests/fixtures/image_pipeline/scenario_09_multi_region`| 8 boxes     |
| `track2_report_p1`         | `output/uploads/5c4224e8/Track-2 Report.pdf` (Page 1)   | 13 boxes    |
| `track2_report_p2`         | `output/uploads/5c4224e8/Track-2 Report.pdf` (Page 2)   | 57 boxes    |
| `track2_report_p3`         | `output/uploads/5c4224e8/Track-2 Report.pdf` (Page 3)   | 95 boxes    |
| `track2_report_p4`         | `output/uploads/5c4224e8/Track-2 Report.pdf` (Page 4)   | 4 boxes     |
| `track2_report_p5`         | `output/uploads/5c4224e8/Track-2 Report.pdf` (Page 5)   | 5 boxes     |
+----------------------------+---------------------------------------------------------+-------------+
| **Total In-Domain Pages**  | **21 Physical Pages**                                   | **487 Boxes**|
+----------------------------+---------------------------------------------------------+-------------+
```

---

## 4. Actual Human-Annotated Examples

* **Total Verified In-Domain Edges:** **204 edges**
* **Annotation Provenance Breakdown:**
  * `in_domain_human_verified`: **204 edges (100.0%)**
  * `in_domain_weak_heuristic`: **0 edges (0.0%)**
* **Held-Out Integrity Mandate:**
  All 204 real in-domain records are assigned exclusively to `splits/test_in_domain.jsonl`.
  **Zero in-domain edges appear in `train.jsonl` or `val.jsonl`.**

---

## 5. Class Distributions by Source

```
+----------------------------------------------------------------------------------------------------+
|                                    CLASS DISTRIBUTIONS BY SOURCE                                   |
+-------------------------------+-----------+-----------+-----------------+-----------+--------------+
| Source Identifier             | PARENT_OF | OPTION_OF | CONTINUATION_OF | NONE      | Total Edges  |
+-------------------------------+-----------+-----------+-----------------+-----------+--------------+
| `funsd_entity_linking`        | 5,293     | 0         | 0               | 0         | 5,293        |
| `funsd_hard_negative`         | 0         | 0         | 0               | 7,886     | 7,886        |
| `synthetic_procedural`        | 2,845     | 8,167     | 2,687           | 0         | 13,699       |
| `synthetic_hard_negative`     | 0         | 0         | 0               | 20,475    | 20,475       |
| `in_domain_human_verified`    | 16        | 36        | 40              | 112       | 204          |
+-------------------------------+-----------+-----------+-----------------+-----------+--------------+
| **Aggregate Dataset Total**   | **8,154** | **8,203** | **2,727**       | **28,473**| **47,557**   |
| **Aggregate Percentages**     | **17.1%** | **17.2%** | **5.7%**        | **59.9%** | **100.0%**   |
+-------------------------------+-----------+-----------+-----------------+-----------+--------------+
```

---

## 6. Label Mapping Decisions & Justification

To maintain technical honesty and prevent semantic distortion:

1. **FUNSD Mapping Decisions:**
   * `header -> question`: Mapped to **`PARENT_OF`**. A structural form header governs the subordinate question fields.
   * `question -> answer`: Mapped to **`PARENT_OF`**. In structured forms, the question (key) is the semantic parent container defining the answer (value) entity.
   * `OPTION_OF` in FUNSD: **Explicitly 0 (Unavailable).** Forms do not contain multiple-choice options $(A, B, C, D)$. We strictly refused to invent `OPTION_OF` labels from form fields.
   * `CONTINUATION_OF` in FUNSD: **Explicitly 0 (Unavailable).** FUNSD entities are self-contained lines/blocks. Multi-line segments are not linked as continuations in the original annotations.
2. **Synthetic Generator Mapping Decisions:**
   * `HEADING -> QUESTION` and `QUESTION -> CODE`: Mapped to **`PARENT_OF`**.
   * `OPTION -> QUESTION`: Mapped to **`OPTION_OF`** (directed child-to-parent option association).
   * Sequential `OPTION -> OPTION` and multi-line question text: Mapped to **`CONTINUATION_OF`**.
   * Cross-question, cross-column, and non-governing entity pairs: Mapped to **`NONE`** via spatial proximity mining ($K$-NN radius $\le 0.35$).
3. **In-Domain Real Mapping Decisions:**
   * Options identified in real test images linked to question blocks: Mapped to **`OPTION_OF`**.
   * Section headers in `Track-2 Report.pdf` linked to paragraphs: Mapped to **`PARENT_OF`**.
   * Sequential paragraphs across column gutters: Mapped to **`CONTINUATION_OF`**.

---

## 7. Canonical Dataset Split Sizes

Splits were constructed using strict **document-level stratification** to ensure zero data leakage:

```
+----------------------------------------------------------------------------------------------------+
|                                    CANONICAL SPLIT SPECIFICATIONS                                  |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| Split File            | Document Cnt. | Total Edges   | Source Composition | Evaluation Purpose    |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| `train.jsonl`         | 349 docs      | 36,346 edges  | FUNSD Train (149)  | Model optimization &  |
|                       |               |               | + Synth Train (200)| gradient updates.     |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| `val.jsonl`           | 75 docs       | 6,584 edges   | FUNSD Test (50)    | Hyperparameter tuning |
|                       |               |               | + Synth Val (25)   | & early stopping.     |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| `test_synthetic.jsonl`| 25 docs       | 4,423 edges   | Synth Test (25)    | Synthetic layout      |
|                       |               |               |                    | generalization test.  |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| `test_in_domain.jsonl`| 21 docs/pages | 204 edges     | Real Images (16)   | **Held-Out Gold Test**|
|                       |               |               | + Track-2 PDF (5)  | (Zero leakage).       |
+-----------------------+---------------+---------------+--------------------+-----------------------+
| **Total SETU-SR**     | **470 Units** | **47,557**    | **Three Streams**  | **Complete Benchmark**|
+-----------------------+---------------+---------------+--------------------+-----------------------+
```

### Detailed Split Class Distribution:
* **`train.jsonl` (36,346 edges):**
  * `PARENT_OF`: 6,300 ($17.3\%$)
  * `OPTION_OF`: 6,279 ($17.3\%$)
  * `CONTINUATION_OF`: 1,999 ($5.5\%$)
  * `NONE`: 21,768 ($59.9\%$)
* **`val.jsonl` (6,584 edges):**
  * `PARENT_OF`: 1,451 ($22.0\%$)
  * `OPTION_OF`: 868 ($13.2\%$)
  * `CONTINUATION_OF`: 323 ($4.9\%$)
  * `NONE`: 3,942 ($59.9\%$)
* **`test_synthetic.jsonl` (4,423 edges):**
  * `PARENT_OF`: 387 ($8.7\%$)
  * `OPTION_OF`: 1,020 ($23.1\%$)
  * `CONTINUATION_OF`: 365 ($8.3\%$)
  * `NONE`: 2,651 ($59.9\%$)
* **`test_in_domain.jsonl` (204 edges):**
  * `PARENT_OF`: 16 ($7.8\%$)
  * `OPTION_OF`: 36 ($17.6\%$)
  * `CONTINUATION_OF`: 40 ($19.6\%$)
  * `NONE`: 112 ($54.9\%$)

---

## 8. Data-Quality Audit & Verification

The automated quality verification suite in `training/structure/assemble_splits.py` produced the following audit results:

```
+----------------------------------------------------------------------------------------------------+
|                                    DATA-QUALITY AUDIT RESULTS                                      |
+------------------------------------+------------------+---------------------+----------------------+
| Quality Dimension Checked          | Verified Value   | Expected Threshold  | Compliance Status    |
+------------------------------------+------------------+---------------------+----------------------+
| Train/Val Document Leakage         | 0 documents      | Exactly 0           | **PERFECT PASS**     |
| Train/Test Synth Leakage           | 0 documents      | Exactly 0           | **PERFECT PASS**     |
| Train/In-Domain Leakage            | 0 documents      | Exactly 0           | **PERFECT PASS**     |
| Invalid Bounding Boxes ($x_1>x_2$) | 0 bounding boxes | Exactly 0           | **PERFECT PASS**     |
| Self-Loop Relationships ($i=j$)    | 0 relationships  | Exactly 0           | **PERFECT PASS**     |
| Feature Vector Dimensionality      | Exactly 15 dims  | Exactly 15 dims     | **PERFECT PASS**     |
| Missing / NaN Coordinate Values    | 0 records        | Exactly 0           | **PERFECT PASS**     |
+------------------------------------+------------------+---------------------+----------------------+
```

---

## 9. Known Limitations & Research Boundaries

1. **Class Asymmetry in Academic Ground Truth:**
   * FUNSD contains zero `OPTION_OF` instances because business forms do not possess multiple-choice examination structures. All `OPTION_OF` supervision is contributed by the procedural synthetic engine and in-domain annotations.
2. **Synthetic Visual Perfection vs. Scanning Noise:**
   * Synthetic layouts generated via Pillow have sharp digital character contours and perfectly rectangular boxes. Real scanned exams (`quest6`–`quest11`) exhibit warping, illumination gradients, and skew.
   * *Mitigation:* `SR-EdgeNet` operates exclusively over normalized spatial coordinates, aspect ratios, and distances ($e_{ij} \in \mathbb{R}^{15}$), rendering the structural classifier invariant to low-level pixel raster noise.
3. **Planar 2D Page Boundary Isolation:**
   * All bounding boxes and relative features are normalized within the bounding canvas of a single page ($W, H$). Cross-page relational links are handled as separate sequential transitions.

---

## 10. Exact Commands to Reproduce Dataset

To completely regenerate and verify the `SETU-SR` dataset from scratch:

```powershell
# 1. Download and process FUNSD academic benchmark
.\.venv\Scripts\python.exe training/structure/download_funsd.py
.\.venv\Scripts\python.exe training/structure/process_funsd.py

# 2. Generate 250 procedural synthetic exam documents
.\.venv\Scripts\python.exe training/structure/synthetic_mcq_generator.py

# 3. Process 16 in-domain project images and Track-2 Report with EasyOCR
.\.venv\Scripts\python.exe training/structure/process_in_domain.py
.\.venv\Scripts\python.exe training/structure/append_track2.py

# 4. Assemble canonical splits and perform quality verification
.\.venv\Scripts\python.exe training/structure/assemble_splits.py

# 5. Run PyTorch DataLoader verification test
.\.venv\Scripts\python.exe training/structure/test_dataset_loader.py
```

---

## 11. Final Assessment & Training Readiness

### **IS THE SETU-SR DATASET READY FOR SR-EdgeNet TRAINING?**

# ✅ YES: THE DATASET IS FULLY CONSTRUCTED, FORMALLY VERIFIED, AND READY FOR TRAINING.

### Definitive Technical Justification:
1. **Sufficient Sample Scale:** We expanded available training edges from **44 to 47,557** ($\approx 1,080\times$ increase), providing an abundant, statistically diverse distribution for a 420k parameter network.
2. **Strict Document-Level Leakage Prevention:** Train, validation, synthetic test, and in-domain test splits are partitioned strictly by document ID. Zero overlap exists between splits.
3. **Independent Real-World Benchmark:** The 204 real in-domain records are 100% held-out in `test_in_domain.jsonl`, establishing an authentic gold-standard benchmark to measure real-world transferability.
4. **PyTorch Integration Tested:** `SETUSREdgeDataset` and `get_dataloader()` have been verified to batch normalized 15-dimensional tensors smoothly without CPU bottlenecks.
