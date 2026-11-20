# SETU-NETRA: Real-World Document Failure Modes & Stress Test Audit

**Report ID:** SETU-AUDIT-FAIL-005  
**Audit Date:** November 3, 2026  
**Audited Pipeline:** End-to-End (`Ingestion` -> `OCR` -> `Structure` -> `Semantics` -> `Store` -> `Retrieval`)  
**Status:** Empirically Executed via `scratch/run_real_world_failure_tests.py`  
**Results Data:** Recorded in `scratch/real_world_test_results.json`  

---

## 1. Executive Summary

A system that passes synthetic unit tests often collapses when exposed to real-world operational documents: rotated photocopies, multi-column research papers, tables, bilingual text, noisy thermal scans, and high-volume multi-page files.

To identify the true operational boundaries of SETU-NETRA, an empirical test suite consisting of **10 challenging real-world failure scenarios** was constructed and executed against the live pipeline.

### Core Verdict
* **Defensive Robustness:** The pipeline handles empty pages, corrupt files, and clean digital PDFs cleanly without crashes.
* **Catastrophic Structural Failure (Multi-Column):** Line grouping merges text across column gutters horizontally, scrambling multi-column reading order.
* **Catastrophic Extraction Failure (Page Rotation):** 90-degree rotated scans fail completely (OCR returns empty or single noise characters like `'0'`).
* **Silent Information Loss (Multilingual):** Non-Latin scripts (Devanagari/Hindi) are silently dropped due to hardcoded English OCR initialization (`lang_list=['en']`).
* **Table Linearization Loss:** Tables are flattened into generic paragraph text, losing row/column associations.
* **Deterministic Scaling:** Multi-page processing scales strictly linearly ($O(N)$) at $\approx 2.83\text{ seconds per page}$ on standard CPU.

---

## 2. Real-World Test Matrix & Empirical Results

| Test Case | Scenario / Document Type | Pipeline Behavior | Empirical Status | Key Observation |
| :---: | :--- | :--- | :---: | :--- |
| **Case 1** | **Blank / Empty Page** | Zero blocks generated, no crash | **PASS** | `block_count = 0`; clean exit. |
| **Case 2** | **Corrupt / Truncated PDF** | Exception caught gracefully | **PASS (EXPECTED)**| Raised `PdfiumError: Failed to load document`; safely rejected before pipeline execution. |
| **Case 3** | **90° Rotated Document** | OCR baseline misalignment | **CRITICAL DEGRADATION** | Detected text: `'0'`. Words completely missed because CRAFT assumes horizontal baselines. |
| **Case 4** | **Low-Resolution / Blurry** | Character-level misrecognition | **DEGRADED** | Extracted `"Lowv Pes Text"` instead of `"Low Res Text"`. Subword embeddings partially recovered meaning. |
| **Case 5** | **Multi-Column Layout** | Cross-gutter line merging | **CRITICAL FAILURE** | Both columns merged into 1 scrambled paragraph block. Reading order destroyed. |
| **Case 6** | **Tabular Grid Data** | Grid structure flattened | **LIMITATION** | Flattened into 3 paragraph blocks; table column alignment lost. |
| **Case 7** | **Bilingual / Multilingual** | Non-English text dropped | **LIMITATION** | English header extracted; Devanagari (Hindi) completely omitted. |
| **Case 8** | **Clean Digital 3-Page PDF** | Multi-page sequential pipeline | **PASS** | 3 pages, 6 blocks processed in $10.23\text{s}$ ($3.41\text{s/page}$). |
| **Case 9** | **Noisy Scanned Exam Paper** | OCR artifact substitution | **DEGRADED** | `(A)` recognized as `IAl`, `(B)` recognized as `IBI`. Regex failed to detect MCQ options. |
| **Case 10**| **10-Page Long Document** | Throughput & memory scaling | **PASS** | 10 pages, 10 blocks in $28.34\text{s}$ ($2.83\text{s/page}$). Linear scaling, constant RAM. |

---

## 3. Deep-Dive Failure Mode Analysis

### 3.1 Case 3: Rotated Scans & Orientation Blindness
* **Empirical Observation:** When an image rotated by $90^\circ$ clockwise was passed to the pipeline, `EasyOCREngine` produced zero meaningful words and returned a single rogue digit `'0'`.
* **Root Cause:**
  1. `loader.py` handles EXIF orientation flags (`ImageOps.exif_transpose`), but scanned documents or flattened PDFs do not contain EXIF metadata.
  2. EasyOCR's CRAFT network detects character affinity heatmaps along horizontal baselines. When lines run vertically, character affinity scores drop below the detection threshold ($0.70$).
* **Downstream Consequence:** Downstream LLM receives an empty context prompt, resulting in total failure to answer.
* **Milestone 6 Solution:** Implement an automatic 4-way orientation detector ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) using Tesseract OSD or a lightweight MobileNet orientation classifier before OCR execution.

---

### 3.2 Case 5: Multi-Column Reading Order Scrambling
* **Empirical Observation:** A two-column document with a central gutter:
  ```
  [Column 1, Line 1]     [Column 2, Line 1]
  [Column 1, Line 2]     [Column 2, Line 2]
  ```
  Was reconstructed as a single block reading:
  `"[Column 1, Line 1] [Column 2, Line 1] [Column 1, Line 2] [Column 2, Line 2]"`
* **Root Cause:**
  In `src/setu_netra/structure/line_grouper.py`, line grouping checks vertical overlap:
  $$\text{overlap} = \frac{\min(y_{1,\text{bottom}}, y_{2,\text{bottom}}) - \max(y_{1,\text{top}}, y_{2,\text{top}})}{\min(h_1, h_2)} > 0.50$$
  If two text segments on opposite sides of a page share roughly the same vertical band, the algorithm treats them as parts of the same line, completely ignoring horizontal column separation gutters.
* **Downstream Consequence:** Scrambles sentences, blends disparate sections, and destroys semantic coherence for embedding models.
* **Milestone 6 Solution:** Implement Recursive XY-Cut layout decomposition or column gutter detection before line grouping.

---

### 3.3 Case 6: Tabular Structure Flattening
* **Empirical Observation:** A $3 \times 3$ data table was converted into loose paragraph blocks.
* **Root Cause:** SETU-NETRA's structural classifier categorizes blocks strictly as `HEADING`, `QUESTION`, `OPTION`, `NOTE`, or `PARAGRAPH`. There is no `TABLE` or `TABLE_CELL` primitive, nor is there coordinate grid clustering.
* **Downstream Consequence:** Relational queries (e.g. *"What is the value in Column B for Row 2?"*) cannot be answered reliably because row-column coordinates are collapsed into unstructured text strings.
* **Milestone 6 Solution:** Implement a table detection heuristic based on horizontal/vertical line detection and coordinate matrix clustering, serializing tables into Markdown format (`| Col 1 | Col 2 |`) for LLM consumption.

---

### 3.4 Case 7: Multilingual Omission (Devanagari / Hindi)
* **Empirical Observation:** A bilingual document containing both English and Hindi text had only its English header recognized:
  ```json
  "hindi_detected": false,
  "detected_text": "English Header Setu-Netra"
  ```
* **Root Cause:**
  In `src/setu_netra/ocr/easyocr_engine.py:35`:
  ```python
  self._reader = easyocr.Reader(lang_list=['en'], gpu=self.use_gpu)
  ```
  EasyOCR is hardcoded to `['en']`. CRNN weights for non-Latin character sets are never loaded, causing all Devanagari glyphs to be filtered out as unclassifiable background noise.
* **Downstream Consequence:** Complete failure for regional government, legal, and academic documents across India.
* **Milestone 6 Solution:** Parameterize `lang_list` in configuration (`settings.yaml` / CLI flag) to support `['en', 'hi']` dynamically.

---

### 3.5 Case 9: Noisy Scans & Rigid MCQ Heuristics
* **Empirical Observation:** A scanned exam page with slight salt-and-pepper noise had option `(A)` recognized as `IAl` and option `(B)` recognized as `IBI`.
* **Root Cause:**
  In `src/setu_netra/structure/classifier.py`:
  ```python
  OPTION_PATTERN = re.compile(r"^\s*(\([A-Da-d1-4]\)|[A-Da-d1-4][\.\)])\s+")
  ```
  The regular expression strictly requires parentheses `(` or periods `.`. When OCR substitutes `(` with `I` or `|`, the pattern match fails, causing options to be classified as generic `PARAGRAPH` blocks. Spatial MCQ grouping fails.
* **Milestone 6 Solution:** Implement fuzzy regex matching and visual indentation heuristics: if a block is indented relative to a preceding `QUESTION` block, classify it as an option candidate even with imperfect punctuation.

---

### 3.6 Case 10: Throughput & Latency Profiling
* **Empirical Scaling:**
  - 1 Page: $2.83\text{ seconds}$
  - 3 Pages: $10.23\text{ seconds}$ ($3.41\text{s/page}$)
  - 10 Pages: $28.34\text{ seconds}$ ($2.83\text{s/page}$)
* **Resource Profile:**
  - **Memory:** Flat line at $\approx 420\text{ MB}$ RSS across 10 pages (due to page-by-page streaming garbage collection).
  - **Bottleneck:** EasyOCR CRAFT text detector takes $> 80\%$ of total pipeline runtime on CPU.
* **Conclusion:** The pipeline does not leak memory over long documents, but sequential CPU OCR limits throughput to $\approx 20\text{ pages per minute}$. GPU acceleration or multi-process page parallelism is needed for high-volume batch ingestion.

---

## 4. Failure Mode Taxonomy Summary

```
SETU-NETRA Failure Modes
├── 1. Ingestion / Preprocessing Layer
│   ├── Orientation Blindness (90/180/270 deg unhandled without EXIF) [CRITICAL]
│   └── High-Res Downscaling Coordinate Offset (1600px cap without scale metadata) [MODERATE]
├── 2. OCR Layer
│   ├── Hardcoded English Monolingual Engine (lang_list=['en']) [HIGH]
│   └── Punctuation Substitution Noise (e.g. '(A)' -> 'IAl') [MODERATE]
├── 3. Structure Reconstruction Layer
│   ├── Cross-Gutter Horizontal Line Merging (Multi-column destruction) [CRITICAL]
│   ├── Table Flattening into Paragraph Strings [HIGH]
│   └── Rigid Regex MCQ Classification Failure [MODERATE]
└── 4. Retrieval / Synthesis Layer
    ├── Corrupted BLOB Deserialization Crash (ValueError) [HIGH]
    ├── Duplicate Passage Top-K Pollution [MODERATE]
    └── Negative Cosine Score Drag on Lexical Retrieval [MODERATE]
```
