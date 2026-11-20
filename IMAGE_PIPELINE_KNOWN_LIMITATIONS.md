# SETU-NETRA V2.0.0-RC1 — Image Pipeline Known Limitations & Failure Boundaries

**Document ID:** `SN-REP-V2-IP-006`  
**Execution Timestamp:** 2026-11-11T23:54:00+05:30  
**Phase:** Boundary Audit & Risk Disclosure  
**Module:** Visual Ingestion, Deep-Learning OCR & Question Solver  
**Status:** AUDITED & FORMALLY DOCUMENTED  

---

## 1. Purpose & Scope

Engineering integrity requires full transparency regarding operational constraints, hardware dependencies, and algorithmic failure modes. This report details the technical boundaries of the SETU-NETRA V2.0.0-RC1 Image-to-Answer pipeline, identifying scenarios where automated extraction or reasoning degrades, how the architecture mitigates these risks, and targeted enhancements for v2.1.0+.

---

## 2. Optical Character Recognition (OCR) Boundaries

### 2.1 Heavily Degraded or Unconstrained Cursive Handwriting
- **Limitation:** While EasyOCR performs exceptionally well on printed documents, semi-printed block handwriting, and clean cursive (such as `sample_question2.jpeg` and `sample_question3.jpeg`), continuous unconstrained cursive handwriting with touching glyphs, highly slanted baselines ($> 30^\circ$), or severe ink bleed can result in character misclassifications (e.g. recognizing `m` as `rn`, or `cl` as `d`).
- **Mitigation:**
  1. The pipeline computes per-box confidence scores. If average word confidence falls below $0.60$, the system issues a warning and sets the epistemic status to `NEEDS_CLARIFICATION`.
  2. The frontend provides an **"Edit Extracted Text"** interactive textarea, allowing human reviewers to correct OCR misreadings before submitting the problem to the reasoning engine.

### 2.2 Low-Contrast or Multi-Colored Text on Complex Backgrounds
- **Limitation:** The CRAFT text detector relies on character affinity heatmaps. When text is written in faint pencil or light yellow ink against low-contrast paper, or printed across intricate watermarks, text regions may be split into fragmented boxes.
- **Mitigation:**
  `safe_composite_on_white` and luminance-weighted grayscale conversion (`to_grayscale`) maximize perceptual stroke contrast based on the ITU-R 601-2 standard.

### 2.3 Complex Nested Mathematical Notation
- **Limitation:** Standard single-line OCR reads mathematical text linearly. Nested 2D structures—such as vertical fractions $\frac{a+b}{c-d}$, multi-line matrices $\begin{pmatrix} a & b \\ c & d \end{pmatrix}$, and nested integrals $\int \int f(x, y) dx dy$—may have their vertical sub-components flattened into ambiguous linear tokens.
- **Mitigation:**
  The `QuestionExtractor` uses mathematical token clustering to preserve superscript carats (`^`), subscripts, and bracket grouping. For advanced LaTeX equations, users can utilize the interactive text review card.

### 2.4 Borderless Multi-Cell Grid Tables
- **Limitation:** Tables lacking visible ruled cell borders rely exclusively on whitespace clustering. If columns have uneven padding or multi-line cell entries, text from adjacent columns can occasionally merge into the same horizontal line grouping.
- **Mitigation:**
  The `DocumentStructureReconstructor` employs vertical column projection slicing (`XY-Cut`) to isolate distinct vertical gutters before performing horizontal line clustering.

---

## 3. Reasoning & Model Execution Boundaries

### 3.1 Local Model (Qwen 3.5 2B) Reasoning Horizon
- **Limitation:** The local `qwen3.5:2b` model is optimized for sub-second, memory-efficient edge execution ($\approx 2.2\text{ GB}$ VRAM / RAM). While highly capable at single-step deduction, SQL clause evaluation, and multiple-choice elimination, it can struggle with multi-stage symbolic mathematical proofs (e.g., higher-order differential equations or multi-table SQL queries involving 5+ recursive CTEs).
- **Mitigation:**
  1. The `AdaptiveModelRouter` automatically estimates task complexity. If the question requires multi-hop reasoning beyond 2B parameters and cloud connectivity is authorized by workspace policy, queries can be routed to larger reasoning models.
  2. The deterministic solver in `ImageQuestionSolver` directly evaluates standard SQL patterns and arithmetic assignments with zero parameter drift.

### 3.2 CPU-Only Execution Latency
- **Limitation:** On machines without CUDA accelerators, EasyOCR runs on CPU via PyTorch. While low-resolution snippets execute in $\approx 800\text{ ms}$, high-resolution multi-column documents ($3000 \times 2200$) require $8\text{ to }11\text{ seconds}$ on CPU.
- **Mitigation:**
  1. Controlled downscaling bounds the maximum dimension to $1600\text{ px}$, preventing exponential $O(N^2)$ convolutional growth.
  2. Synchronous OCR and inference tasks are offloaded to background worker threads via `anyio.to_thread.run_sync` with bounded concurrency limiters, ensuring the FastAPI ASGI event loop remains completely unblocked.
  3. The frontend displays real-time animated lifecycle progress badges (`IMAGE_UPLOADED` $\to$ `OCR_PROCESSING` $\to$ `QUESTION_IDENTIFIED` $\to$ `ANSWER_GENERATING` $\to$ `ANSWER_COMPLETED`) so users always have live visibility into pipeline execution.

---

## 4. Operational Boundaries Summary

| Feature / Scenario | Operational Boundary | System Behavior / Fallback |
| :--- | :--- | :--- |
| **Max Image Dimensions** | $100\text{ Megapixels}$ ($100,000,000\text{ pixels}$) | Immediate rejection via `DecompressionBombError` |
| **Downscaling Threshold** | $> 1600\text{ px}$ max dimension | Rescaled via Lanczos; coordinates mapped back to canvas |
| **Minimum Dimension** | $< 400\text{ px}$ | Processed natively without artificial interpolation |
| **OCR Confidence Floor** | $< 0.60$ average confidence | Tagged `NEEDS_CLARIFICATION`; editable in UI |
| **File Formats** | PNG, JPG, JPEG, TIFF, BMP, WEBP | Magic-byte verified; unsupported formats rejected |
| **Inference Timeout** | $60\text{ seconds}$ default per query | Bounded thread pool cancellation with RFC 9457 error |

---

## 5. Roadmap for V2.1.0 Enhancements

1. **LaTeX Mathpix/Nougat Integration:** Introduce optional specialized transformer models for 2D mathematical fractions and matrix parsing.
2. **Table Transformer (TATR):** Add semantic cell-border prediction for borderless scientific tables.
3. **GPU Auto-Detection:** Automatically enable half-precision FP16 TensorRT inference when NVIDIA CUDA hardware is detected, reducing OCR latency from $7\text{s}$ to $< 400\text{ms}$.
4. **Interactive Bounding Box Splitting:** Allow users to drag, split, or merge OCR bounding boxes directly on the spatial canvas prior to question identification.
