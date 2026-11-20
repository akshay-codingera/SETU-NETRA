# SETU-NETRA: Milestone 6 Sprint 1 Implementation & Verification Report

**Report ID:** SETU-M6-SPRINT1-001  
**Date:** November 6, 2026  
**Sprint Focus:** Retrieval Reliability, Defensive Persistence, & Duplicate Suppression  
**Status:** Implemented, Tested, & Empirically Verified (90/90 Passing Tests)  

---

## 1. Executive Summary

Milestone 6 Sprint 1 addressed three high-priority reliability vulnerabilities identified during the Milestone 5 architectural audit:

1. **Defensive Embedding Deserialization:** In `src/setu_netra/store/sqlite_store.py`, reading truncated, byte-misaligned, or corrupted embedding BLOBs previously threw an unhandled `ValueError`, crashing retrieval across the entire database. This has been resolved with strict byte-alignment verification, dimension consistency validation, non-finite (NaN/Inf) screening, and defensive skipping with diagnostic logging.
2. **Dense Score Regularization (Negative Drag Elimination):** In `src/setu_netra/retrieval/document_retriever.py`, raw cosine similarities in $[-1.0, 1.0]$ were linearly combined with lexical scores in $[0.0, 1.0]$. When a candidate had an exact keyword match ($S_{\text{lexical}} = 0.80$) but negative semantic cosine ($S_{\text{dense}} = -0.30$), the negative score dragged down the hybrid score to $0.03$, causing false-negative omission below the $0.20$ threshold. This has been resolved via non-negative rectification ($\text{ReLU}$).
3. **Duplicate Passage & Repeated Header Suppression:** Repeated exam headers, instructions, and duplicate blocks across multi-page documents previously saturated all top-$K$ search slots. This has been resolved via a dual-metric text similarity filter combining token Jaccard screening and character SequenceMatcher alignment.

---

## 2. Modified Files & Functions Inventory

| File | Functions / Classes Modified | Type of Change | Backwards Compatible? |
| :--- | :--- | :--- | :---: |
| [`src/setu_netra/store/sqlite_store.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/store/sqlite_store.py) | `SQLiteDocumentStore.__init__`<br>`_record_skipped_embedding`<br>`get_last_skipped_embeddings`<br>`get_all_embeddings` | Defensive BLOB validation, error logging, and diagnostic reporting | **Yes** (Exact return tuple preserved) |
| [`src/setu_netra/retrieval/document_retriever.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/retrieval/document_retriever.py) | `rectify_dense_score`<br>`compute_lexical_similarity`<br>`compute_hybrid_score`<br>`compute_text_similarity`<br>`DocumentRetriever.__init__`<br>`DocumentRetriever.retrieve`<br>`DocumentRetriever.last_suppressed_duplicates` | Rectified dense scoring, independent scoring modes, configurable $\alpha$, and near-duplicate suppression | **Yes** (All new parameters have safe defaults) |
| [`tests/test_embedding_corruption.py`](file:///d:/Projects/Setu-Netra/tests/test_embedding_corruption.py) | `TestEmbeddingCorruptionHandling` (6 tests) | New test suite for persistence corruption edge cases | **New File** |
| [`tests/test_hybrid_score_robustness.py`](file:///d:/Projects/Setu-Netra/tests/test_hybrid_score_robustness.py) | `TestHybridScoreRobustness` (8 tests) | New test suite for dense score robustness & score drag | **New File** |
| [`tests/test_duplicate_suppression.py`](file:///d:/Projects/Setu-Netra/tests/test_duplicate_suppression.py) | `TestDuplicateSuppression` (7 tests) | New test suite for duplicate & repeated header suppression | **New File** |

---

## 3. Mathematical Reasoning Behind Score Changes

### 3.1 The Negative Cosine Drag Problem

In unit-normalized vector spaces ($\|q\|_2 = 1.0, \|v\|_2 = 1.0$), raw cosine similarity is:
$$S_{\text{dense}}(q, v) = q \cdot v = \cos(\theta_{q, v}) \in [-1.0, 1.0]$$

Lexical term overlap (cosine coefficient over token sets) is non-negative:
$$S_{\text{lexical}}(Q, B) = \frac{|Q \cap B|}{\sqrt{|Q| \cdot |B|}} \in [0.0, 1.0]$$

Under the legacy formula:
$$S_{\text{hybrid}} = \alpha \cdot S_{\text{dense}} + (1 - \alpha) \cdot S_{\text{lexical}}$$

Consider a technical query containing a rare variable name or specific error code:
* $S_{\text{lexical}} = 0.80$ (exact token match)
* $S_{\text{dense}} = -0.30$ (neural model maps code token to opposing semantic half-space)
* With $\alpha = 0.70$:
  $$S_{\text{hybrid}} = 0.70 \times (-0.30) + 0.30 \times 0.80 = -0.21 + 0.24 = \mathbf{0.03}$$

Because $0.03 < \text{threshold } (0.20)$, the candidate is dropped! The negative cosine score **actively penalized** exact keyword evidence.

### 3.2 Mathematical Justification for Rectification (ReLU)

In high-dimensional sentence embedding spaces (e.g. 384 dimensions), unrelated sentences cluster near $0.0$. Negative cosine values indicate that vectors point into opposite half-spaces; they do **not** represent affirmative evidence of factual contradiction that should override exact lexical keyword presence. Negative semantic similarity represents an *absence of semantic evidence*, not *evidence of absence*.

Therefore, we apply non-negative rectification:
$$S_{\text{dense, norm}} = \max(0.0, \min(1.0, S_{\text{dense}}))$$

Under this formulation:
1. **Linear Fidelity Preserved:** For all positive semantic matches ($S_{\text{dense}} \ge 0$), the relative differences, gradients, and ranking order are strictly preserved.
2. **Elimination of Score Drag:** When $S_{\text{dense}} < 0$, the semantic contribution is bounded at $0.0$. It provides $0$ points rather than subtracting points.
3. **Commensurate Score Ranges:** Both $S_{\text{dense, norm}} \in [0.0, 1.0]$ and $S_{\text{lexical}} \in [0.0, 1.0]$.
4. **Guaranteed Bounded Hybrid Score:**
   $$S_{\text{hybrid}} = \alpha \cdot S_{\text{dense, norm}} + (1 - \alpha) \cdot S_{\text{lexical}} \in [0.0, 1.0]$$

With rectification, the earlier candidate achieves:
$$S_{\text{hybrid}} = 0.70 \times 0.0 + 0.30 \times 0.80 = \mathbf{0.24} \ge 0.20 \quad (\text{ACCEPTED})$$

---

## 4. Duplicate Suppression Algorithm

To eliminate repeated headers without suppressing distinct questions that share vocabulary, `compute_text_similarity` uses a multi-stage approach:

1. **Exact String Match:** Normalized whitespace and lowercase comparison $\to S_{\text{text}} = 1.0$.
2. **Token Jaccard Screening:**
   $$J(T_1, T_2) = \frac{|T_1 \cap T_2|}{|T_1 \cup T_2|}$$
   If $J < 0.35$, the passages are largely disjoint $\to$ immediate early return ($S_{\text{text}} = J$).
3. **Sequence Alignment Blending:**
   For overlapping passages, compute Python's Ratcliff-Obershelp sequence alignment ratio $R_{\text{seq}} = \text{SequenceMatcher}(T_1, T_2).\text{ratio}()$.
   Combine via weighted interpolation:
   $$S_{\text{text}} = 0.40 \cdot J(T_1, T_2) + 0.60 \cdot R_{\text{seq}}$$

### Threshold Calibration:
* **Repeated Page Headers:** (e.g. `"... PAGE 1"` vs `"... PAGE 2"`): $S_{\text{text}} = 0.918 \ge 0.85$ $\to$ **Suppressed**.
* **Typographical Noise / Typos:** (e.g. `"ballpoint"` vs `"ball-point!"`): $S_{\text{text}} = 0.893 \ge 0.85$ $\to$ **Suppressed**.
* **Distinct Questions with Common Phrasing:**
  - $Q_1$: *"What is the time complexity of bubble sort in worst case?"*
  - $Q_2$: *"What is the space complexity of quick sort in average case?"*
  - Score: $S_{\text{text}} = 0.694 < 0.85$ $\to$ **NOT Suppressed** (Both preserved).

---

## 5. Before vs. After Empirical Comparison

| Scenario | Input Query & Document Context | Legacy Baseline (Before) | Milestone 6 Sprint 1 (After) | Status |
| :--- | :--- | :--- | :--- | :---: |
| **1. Truncated Embedding BLOB** | Malformed BLOB with 17 bytes in database | `ValueError: buffer size must be a multiple of element size` (Entire query crashed) | Skips malformed row, logs diagnostic warning, retrieves valid rows | **FIXED** |
| **2. NaN / Inf Vector** | Vector containing `np.nan` or `np.inf` | Produced NaN dot products and corrupted ranking | Flagged as `non_finite_values`, recorded in diagnostics, skipped | **FIXED** |
| **3. Negative Cosine Score Drag** | Query: *"hyperparameter tuning configuration"*<br>Raw dense: $-1.0$, Lexical: $0.77$ | $S_{\text{hybrid}} = -0.469 < 0.15$<br>Result: **0 blocks returned (Dropped)** | $S_{\text{hybrid}} = 0.231 \ge 0.15$<br>Result: **1 block returned (Retrieved)** | **FIXED** |
| **4. Repeated Exam Headers** | Query matching 3-page exam header | Top 3 slots occupied by identical header from Pages 1, 2, and 3 | Header from Page 1 retained; Pages 2 and 3 suppressed into diagnostics; top-K filled with questions | **FIXED** |
| **5. Cross-Document Duplicates** | Identical legal disclaimer in Document A and Document B | Both copies returned in Top-K | Only 1 copy returned; duplicate suppressed with cross-document provenance logged | **FIXED** |

---

## 6. Test Suite Execution & Verification

### Test Breakdown:
* **Original Milestone 1–5 Suite:** 69 tests (`Ran 69 tests ... OK`).
* **Embedding Corruption Suite (`test_embedding_corruption.py`):** 6 tests (`Ran 6 tests in 0.164s ... OK`).
* **Hybrid Score Robustness Suite (`test_hybrid_score_robustness.py`):** 8 tests (`Ran 8 tests in 0.138s ... OK`).
* **Duplicate Suppression Suite (`test_duplicate_suppression.py`):** 7 tests (`Ran 7 tests in 0.113s ... OK`).

### Full Combined Suite Output:
```text
$env:PYTHONPATH="src"; .venv\Scripts\python -m unittest discover -s tests

.........Skipping malformed embedding for Doc doc_test_corruption, Page 1, Block 3: malformed_blob_length: byte length 17 is not a multiple of 4
.Embedding dimension mismatch for Doc doc_test_corruption, Page 1, Block 4: dimension_mismatch: metadata indicates 384 dims, but blob has 64
.Embedding contains NaN or Inf for Doc doc_test_corruption, Page 1, Block 5: non_finite_values: nan=True, inf=False
Embedding contains NaN or Inf for Doc doc_test_corruption, Page 1, Block 6: non_finite_values: nan=False, inf=True
.Skipping malformed embedding for Doc doc_test_corruption, Page 1, Block 2: malformed_blob_length: byte length 19 is not a multiple of 4
Embedding contains NaN or Inf for Doc doc_test_corruption, Page 1, Block 4: non_finite_values: nan=True, inf=False
....................................................................................
----------------------------------------------------------------------
Ran 90 tests in 29.890s

OK
```

---

## 7. Remaining Limitations & Sprint 2 Priorities

While retrieval stability, scoring robustness, and duplicate filtering are now secured, the structural and visual limitations identified in the audit remain to be tackled in Sprint 2:

1. **Multi-Column Reading Order:** Horizontal line grouping across column gutters remains unaddressed. Sprint 2 must implement Recursive XY-Cut layout segmentation.
2. **Page Orientation (OSD):** Scans rotated by $90^\circ$ still fail OCR. Sprint 2 must implement 4-way visual orientation detection.
3. **Monolingual OCR Engine:** EasyOCR remains initialized with `['en']`. Sprint 2 will introduce dynamic language configuration (`['en', 'hi']`).
4. **Dual-Coordinate Storage:** Bounding boxes remain stored in $150\text{ DPI}$ pixel coordinates without normalized $[0.0, 1.0]$ unit coordinates.
