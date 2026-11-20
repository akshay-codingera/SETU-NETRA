# SETU-NETRA V2.0.0-RC1 — Image-to-Answer Pipeline Root Cause & Architecture Inspection Report

**Document ID:** `SN-REP-V2-IP-001`  
**Execution Timestamp:** 2026-11-11T23:15:00+05:30  
**Phase:** Diagnostic Audit (Milestone: Complete Image-to-Answer Pipeline)  
**Author:** Lead Full-Stack AI Systems Engineering  

---

## 1. Executive Summary

A comprehensive architectural and code-level audit was conducted across all subsystems involved in the image-to-question-to-answer lifecycle:
- Image upload and ingestion (`/api/v1/documents/upload` & `document_pipeline.py`)
- Image validation and preprocessing (`validator.py`, `loader.py`, `operations.py`)
- Deep-learning OCR execution (`easyocr_engine.py`)
- Geometric layout reconstruction (`reconstructor.py`, `line_grouper.py`, `block_grouper.py`)
- Relational persistence and schema indexing (`sqlite_store.py`)
- Intelligence QA request routing (`query.py` & `qa/engine.py`)
- Model orchestration & SQL semantic understanding (`router.py`, `question_extractor.py`)
- Frontend state management and presentation (`DocumentIntelligenceView.tsx`)

The audit revealed that while individual foundational algorithms exist in isolation, **critical information is discarded at subsystem boundaries**, preventing uploaded images from reliably converting into verified answers.

---

## 2. Root Cause Analysis by Component

### 2.1 Image Dimension Handling & Spatial Coordinate Desynchronization
- **Location:** `src/setu_netra/pipeline/document_pipeline.py:178-235` & `src/setu_netra/preprocessing/operations.py:53-98`
- **Symptom:** Bounding boxes on the spatial canvas are shrunken or displaced relative to the document image.
- **Root Cause:**
  When `proc_img = resize_keep_aspect_ratio(proc_img, max_dimension=cfg.max_dimension)` scales down a high-resolution image (e.g., from $2400 \times 3200$ to $1200 \times 1600$), EasyOCR computes bounding boxes in the downscaled coordinate space ($[0..1200, 0..1600]$).
  However, `self.store.save_page` persists the original image dimensions ($W=2400, H=3200$), while `self.store.save_blocks` persists the unadjusted downscaled bounding boxes ($[xmin, ymin, xmax, ymax]$).
  When the frontend calculates percentage offsets:
  $$\text{left} = \left(\frac{x_{\min}}{W_{\text{page}}}\right) \times 100\% = \left(\frac{x_{\min}}{2400}\right) \times 100\%$$
  The bounding boxes are scaled by an erroneous factor of 2, appearing at half size and completely misaligned.
- **Remedy:** Maintain a formal coordinate transformation matrix $(S_x, S_y, \Delta x, \Delta y)$ between original and processed images, mapping all bounding boxes back to the original coordinate space prior to storage.

### 2.2 Incomplete OCR Page Reconstruction & Information Loss
- **Location:** `src/setu_netra/pipeline/document_pipeline.py:198-250` & `src/setu_netra/store/sqlite_store.py`
- **Symptom:** The platform only exposes isolated bounding boxes; full-page text, reading order, and question structures are missing.
- **Root Cause:**
  `DocumentStructureReconstructor.reconstruct()` properly generates a complete `DocumentStructureResult` containing `raw_transcript`, `questions`, and `lines`.
  However, `document_pipeline.py` discards `struct_res.raw_transcript` and `struct_res.questions`! It solely extracts `block_records` and saves them to `document_blocks`.
  The `pages` table's `metadata_json` only records `{"block_count": len(block_records)}`. The complete page transcription is never persisted in SQLite or returned by `/api/v1/documents/{doc_id}/pages`.
- **Remedy:** Persist `full_text`, `raw_ocr_transcript`, `detected_questions`, and confidence statistics in `pages.metadata_json` and add a dedicated `GET /api/v1/documents/{doc_id}/pages/{page_number}/text` API endpoint.

### 2.3 Transparent & Exotic Image Format Handling
- **Location:** `src/setu_netra/ingestion/loader.py` & `src/setu_netra/api/routers/documents.py:316-324`
- **Symptom:** PNGs with alpha channels render with black backgrounds or corrupted text; smartphone photos with EXIF tags display sideways or upside-down.
- **Root Cause:**
  When converting an `RGBA` or `P` (palette with alpha) image directly via `.convert("RGB")`, transparent pixels become black (`#000000`). If dark ink was written over transparent backgrounds, the text is completely obliterated by black pixels.
  Furthermore, `POST /api/v1/query/image` in `query.py` loaded raw bytes via `Image.open(io.BytesIO(contents)).convert("RGB")` without calling `ImageOps.exif_transpose`, resulting in inverted OCR when smartphone photos are uploaded.
- **Remedy:** Implement composite alpha-to-white blending (`Image.alpha_composite` over a white canvas) and enforce `ImageOps.exif_transpose` across all image endpoints.

### 2.4 Disconnected Intelligence QA & Document Search Anti-Pattern
- **Location:** `src/setu_netra/api/routers/query.py:125-185` & `src/setu_netra/qa/engine.py:110-139`
- **Symptom:** Uploading a question image yields `UNSUPPORTED` (*"The uploaded document does not contain sufficient verified evidence to answer this question"*).
- **Root Cause:**
  The existing `POST /api/v1/query/image` treated the uploaded image text as a **search query** to run against a document retriever.
  If an investigator uploads an image containing an SQL or math exam problem, the system searches the workspace corpus for documents discussing that exact text. Since the question itself is the problem to be solved, the retriever finds no matching passages ($G_s = 0.0$), and `EvidenceGroundedQAEngine` immediately aborts with `epistemic_status = "UNSUPPORTED"`.
- **Remedy:** Implement an explicit **Direct Problem Solving & Reasoning Pipeline** that recognizes when an uploaded image is a self-contained question/problem, dispatches it to the model router with structured domain instructions, evaluates multiple-choice options, and verifies the solution.

### 2.5 Lack of SQL Semantic Understanding & Option Analysis
- **Location:** `src/setu_netra/qa/question_extractor.py` & `src/setu_netra/routing/adapters/`
- **Symptom:** SQL multiple-choice questions are treated as generic text; options are jumbled into the prompt, and the model selects options based on keyword frequency rather than relational semantics.
- **Root Cause:**
  The system lacked domain-specific question classifiers for SQL. When an SQL question is parsed, the system failed to:
  1. Separate question requirements (e.g. `WHERE Age > 10`, `GROUP BY Group`, `COUNT(*)`) from candidate queries.
  2. Differentiate `GROUP BY` from `ORDER BY`.
  3. Formally evaluate each candidate option (A, B, C, D) against the semantic requirements.
  4. Explain why the selected query is correct and why other options are invalid.
- **Remedy:** Implement dedicated `SQLQuestionSolver` and enhanced `QuestionExtractor` capable of identifying SQL, mathematical, and programming questions, parsing options cleanly, and evaluating them with step-by-step semantic justification.

### 2.6 Frontend Fragmentation & Absence of "Identify and Answer" Workflow
- **Location:** `frontend/src/views/DocumentIntelligenceView.tsx`
- **Symptom:** Users in the Documents workspace can view images and click individual blocks, but cannot view full extracted text, view identified questions, edit transcription errors, or trigger answer generation.
- **Root Cause:**
  The `DocumentIntelligenceView` component was strictly a passive layout viewer. It had no state for full page text, no question identification card, and no direct integration with the QA solver.
- **Remedy:** Integrate an active **Question-to-Answer Panel** directly inside `DocumentIntelligenceView.tsx`, providing:
  - Complete Extracted Text view (editable prior to submission)
  - Reconstructed Question & Answer Options breakdown
  - One-click "Identify and Answer" button
  - Epistemic verification, answer display, and SQL/domain explanations.

---

## 3. Architecture Action Plan

```
+-------------------------------------------------------------------------------+
|                        REPAIRED PIPELINE ARCHITECTURE                         |
+-------------------------------------------------------------------------------+
                                        |
 1. Image Ingestion & Normalization     | - EXIF Transpose & Alpha-to-White Composite
                                        | - Max-Dimension Aspect-Preserved Scaling
                                        | - Coordinate Mapping Matrix (Sx, Sy)
                                        v
 2. Enhanced Page OCR & Reconstruction  | - EasyOCR + Contrast & Deskew Filters
                                        | - Line & Multi-Column Spatial Grouping
                                        | - Full Page Transcript Persistence
                                        v
 3. Question & Option Identification    | - Detects MCQ, Direct, SQL, Math, Code
                                        | - Normalizes Options (A, B, C, D)
                                        | - Identifies Ambiguities & Low-Conf Tokens
                                        v
 4. Domain-Aware Question Solver        | - Relational SQL Clause Verification
                                        | - Option Elimination & Justification
                                        | - Qwen 3.5 2B / Adaptive Model Routing
                                        v
 5. Unified Frontend Experience         | - Editable OCR Full Text
                                        | - "Identify and Answer" Action Button
                                        | - Spatial Canvas + Block Inspector Intact
+-------------------------------------------------------------------------------+
```

---

## 4. Verification Checkpoint

This diagnostic audit confirms that the core ML foundations (EasyOCR, sentence transformers, Qwen 3.5 2B, and SQLite) are sound and do not require replacement. The repairs focus entirely on **pipeline continuity, coordinate normalization, structured question extraction, SQL semantic reasoning, and unified presentation**.
