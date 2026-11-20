# OCR Structural Accuracy & End-to-End Test Suite

**Document Version:** 1.0.0  
**Test Suite:** `tests/test_structure.py`, `tests/test_domain_solvers.py`  
**Execution Environment:** Windows 11, Python 3.14.7, pytest-9.2.0, CPU Inference  
**Date:** November 12, 2026  

---

## 1. Test Suite Summary

The structural reconstruction and domain-aware answering pipeline were verified across 16 test cases, including synthetic geometry benchmarks and physical high-resolution handwritten test artifacts (`quest6.png`, `quest7.png`, `quest8.png`).

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Projects\Setu-Netra
tests/test_structure.py ..........                                       [100%]
tests/test_domain_solvers.py ......                                      [100%]
============================= 16 passed in 0.28s ==============================
```

---

## 2. Detailed Test Specifications & Results

### Test Group A: Geometric & Reading-Order Unit Tests (`tests/test_structure.py`)
| Test ID | Test Target | Input Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | `test_reading_order_sorting` | 5 vertically jittered lines | Strict top-to-bottom line reading order | **PASSED** |
| **T02** | `test_multi_column_detection` | Two distinct column bounding boxes | Column boundary detection with gutter isolation | **PASSED** |
| **T03** | `test_question_option_association` | Q1 followed by [A], [B], [C], [D] | Valid QuestionGroup with 4 child options | **PASSED** |
| **T04** | `test_heading_classification` | Large font title vs body text | BlockType.HEADING correctly assigned | **PASSED** |
| **T05** | `test_list_item_classification` | Numbered and bulleted list items | BlockType.LIST_ITEM correctly assigned | **PASSED** |
| **T06** | `test_handwriting_ocr_artifacts` | OCR artifacts `IBJ`, `ID]`, `d2` | Normalized to standard labels B, D | **PASSED** |
| **T07** | `test_non_consecutive_options` | Options [A], [C], [D] (missing B) | Warning flagged for missing label B | **PASSED** |
| **T08** | `test_adaptive_scale_computation`| Mixed scale text detections | Adaptive scale and median line height | **PASSED** |
| **T09** | `test_geometry_overlap_metrics` | Intersecting vs disjoint boxes | Correct vertical overlap ratios | **PASSED** |
| **T10** | `test_low_confidence_filtering` | Detections below 0.25 confidence | Classified as UNCLASSIFIED with warning | **PASSED** |

---

### Test Group B: Physical Handwritten Ingestion Tests

#### Artifact 1: `quest6.png` (Arithmetic Assignment Ingestion)
- **Input:** Handwritten note `Question_ Given : a = 10 ; b = 5 ; result = a + b - 23 + 40 ; What is the Value of result?`
- **Domain:** `ARITHMETIC` / `PROGRAMMING`
- **Evaluator:** AST Safe Arithmetic Evaluator
- **Proof:** $10 + 5 = 15 \to 15 - 23 = -8 \to -8 + 40 = 32$
- **Result:** `32`
- **Epistemic Status:** `COMPUTATION_VERIFIED`
- **Status:** **PASSED**

#### Artifact 2: `quest7.png` (SQL Multiple-Choice Ingestion)
- **Input:** Handwritten query selection with 4 multi-line SQL options.
- **Line Clustering:** 16 clean lines assembled via neighbor-chain tracking without horizontal word interleaving.
- **Block Segmentation:** Block 1 (Question), Block 2 (Option A), Block 3 (Option B), Block 4 (Option C), Block 5 (Option D).
- **Domain:** `SQL`
- **Evaluator:** Relational Algebra Evaluation Engine
- **Selection:** `Option A`
- **Epistemic Status:** `LOGIC_VERIFIED`
- **Status:** **PASSED**

#### Artifact 3: `quest8.png` (Categorical Syllogism Ingestion)
- **Input:** Handwritten syllogism with 3 premises and 4 conclusions.
- **Domain:** `LOGICAL_REASONING`
- **Evaluator:** Set-Theoretic Countermodel Prover
- **Result:** Proved that none of the 4 conclusions is definitely entailed; verified Option C as POSSIBLY_TRUE ("may be").
- **Epistemic Status:** `LOGIC_VERIFIED`
- **Status:** **PASSED**
