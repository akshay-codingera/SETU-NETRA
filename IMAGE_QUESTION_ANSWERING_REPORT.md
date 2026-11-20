# SETU-NETRA V2.0.0-RC1 — Image Question Answering & Reasoning Architecture Report

**Document ID:** `SN-REP-V2-IP-005`  
**Execution Timestamp:** 2026-11-11T23:53:00+05:30  
**Phase:** Visual Question Answering & Semantic Reasoning Audit  
**Module:** Question Extractor, Relational SQL Reasoner & Epistemic Verifier  
**Status:** IMPLEMENTED, INTEGRATED & VERIFIED  

---

## 1. Executive Summary

This report provides the technical design, lifecycle state engine, relational reasoning logic, and epistemic verification mechanisms governing SETU-NETRA's image question-answering architecture.

Prior to this implementation, image uploads were treated as document search queries, resulting in `UNSUPPORTED` responses when users uploaded self-contained exam problems or database queries. SETU-NETRA V2.0.0-RC1 introduces a dedicated **Direct Problem Solving & Reasoning Engine** (`ImageQuestionSolver`) integrated with `QuestionExtractor`, `AdaptiveModelRouter`, and the interactive frontend workspace.

---

## 2. Eight-State Question Lifecycle Engine

The image-to-answer flow transitions deterministically through 8 granular lifecycle states:

```
[1. IMAGE_UPLOADED]
        |
        v
[2. OCR_PROCESSING] --------(Empty OCR / Noise)--------> [8. PROCESSING_FAILED]
        |
        v
[3. OCR_COMPLETED]
        |
        v
[4. QUESTION_IDENTIFIED] ---(Ambiguous / Incomplete)---> [7. NEEDS_CLARIFICATION]
        |
        v
[5. ANSWER_GENERATING]
        |
        v
[6. ANSWER_VERIFICATION]
        |
        v
[9. ANSWER_COMPLETED]
```

### 2.1 State Definitions

| State | Identifier | Description & Exit Criteria |
| :---: | :--- | :--- |
| **1** | `IMAGE_UPLOADED` | Raw image bytes received, magic-byte validated, EXIF-normalized, and decompressed into memory. |
| **2** | `OCR_PROCESSING` | Text detection (CRAFT) and recognition (CRNN) executing across the normalized canvas. |
| **3** | `OCR_COMPLETED` | Spatial bounding boxes, line groupings, and raw transcript assembled. |
| **4** | `QUESTION_IDENTIFIED`| Question stem, options, domain (`SQL`, `MATHEMATICAL`, `PROGRAMMING`, `GENERAL`), and format extracted. |
| **5** | `ANSWER_GENERATING` | Relational reasoning, mathematical assignment evaluation, or LLM inference dispatch in progress. |
| **6** | `ANSWER_VERIFICATION` | Candidate solution evaluated against extracted options, relational constraints, and confidence metrics. |
| **7** | `ANSWER_COMPLETED` | Verified final answer, selected option, step-by-step reasoning, and option elimination matrix published. |
| **8** | `NEEDS_CLARIFICATION`| Insufficient information in image (e.g. truncated question or illegible handwriting); flagged for human review. |
| **9** | `PROCESSING_FAILED` | File corrupt, decompression limit exceeded, or unrecoverable error encountered. |

---

## 3. SQL Relational Reasoning Engine

SETU-NETRA features dedicated semantic understanding for database queries, going beyond surface-level text generation to model actual relational algebra.

### 3.1 Clause Dissection & Normalization
The `parse_sql_clauses(text)` function extracts relational query components using resilient regex patterns that tolerate common OCR substitutions:
- `SELECT`: Column projections, wildcards (`*`), or aggregate functions (`COUNT(*)`, `SUM(salary)`).
- `FROM`: Source table or joined relations.
- `WHERE`: Filter predicates evaluated per tuple prior to aggregation.
- `GROUP BY`: Partitioning keys creating grouped equivalence classes.
- `HAVING`: Post-aggregation filter predicates.
- `ORDER BY`: Sorting specifications (`ASC` / `DESC`).

### 3.2 Relational Semantics vs Keyword Matching
A naive LLM or keyword matcher often confuses `GROUP BY` with `ORDER BY` because both re-organize query results. SETU-NETRA implements relational semantic rules:

1. **Aggregation & Grouping Verification:**
   - If `GROUP BY col` is present: The query groups rows sharing identical values in `col` and applies aggregate functions per partition.
   - Contrast with `ORDER BY`: Does not reduce cardinality or group rows; only sorts output presentation order.
2. **Filtering Verification:**
   - If `WHERE cond` is present: Filters individual candidate tuples before grouping or projection.
3. **Option Elimination Matrix:**
   Every option ($A, B, C, D$) is formally evaluated against the query semantics:
   ```json
   {
     "A": "Correct: Query groups rows by department and calculates COUNT(*) per group.",
     "B": "Incorrect: Query does not select employee names; it projects department and count.",
     "C": "Incorrect: Query does not compute salary sums; only row count is aggregated.",
     "D": "Incorrect: Query groups data rather than returning unaggregated table tuples."
   }
   ```

---

## 4. Mathematical & Programming Variable Assignment Solver

For quantitative problems (such as `sample_question4.jpeg`), the solver models program state:
1. **Variable Extraction:** Parses assignments `Integer a = 20; Integer b = 50;`.
2. **Formula Parsing:** Identifies equations `Sum = b - a` even when OCR drops operators (e.g. `Sum =b a`).
3. **Deterministic Evaluation:** Computes $50 - 20 = 30$.
4. **Option Matching:** Maps $30$ to Option D, generating an explanation:
   - *Step 1: Parse variables from problem statements: b = 50, a = 20.*
   - *Step 2: Evaluate the specified formula Sum = b - a = 50 - 20 = 30.*
   - *Step 3: Compare computed result (30) with available options.*

---

## 5. Epistemic Verification & Confidence Scoring

Every generated answer is assigned an **Epistemic Status** reflecting its mathematical certainty:

| Epistemic Status | Criteria | Visual Hanko Seal in UI |
| :--- | :--- | :---: |
| `VERIFIED_GROUNDED` | Formally proven via deterministic relational/arithmetic evaluation or $>0.90$ model confidence. | Green Grounded Hanko |
| `EXTRACTED` | Directly extracted from unambiguous document text without synthetic deduction. | Blue Extracted Hanko |
| `NEEDS_CLARIFICATION`| Ambiguous options, low OCR confidence ($<0.60$), or multiple plausible interpretations. | Amber Advisory Hanko |
| `UNSUPPORTED` | Question references external concepts not grounded in the uploaded document image. | Red Unsupported Hanko |

---

## 6. Frontend Workspace Integration

The user interface in `frontend/src/views/DocumentIntelligenceView.tsx` provides an interactive 3-column workspace:

```
+----------------------------------------------------------------------------------------------------+
|                                    DOCUMENTS & SPATIAL WORKSPACE                                   |
+--------------------------+-------------------------------------+-----------------------------------+
| 1. Document Corpus (3 col)| 2. Spatial Canvas Overlay (5 col)   | 3. Question & Answer Solver (4 col)|
|                          |                                     |                                   |
| - Document Selector      | - High-Resolution Image Canvas      | - OCR Text (Review / Edit toggle) |
| - Page Navigation        | - Rescaled Bounding Box Overlay     | - Model Selector (qwen / auto)    |
| - Upload Document Modal  | - Coordinate Synchronization        | - "Identify and Answer" Button    |
| - Document Status List   | - Hover / Selection Indicators      | - Lifecycle Progress Badge        |
|                          |                                     | - Reconstructed Question Card     |
|                          |                                     | - Multiple-Choice Options List    |
|                          |                                     | - Final Verified Answer Banner    |
|                          |                                     | - Step-by-Step Reasoning Flow     |
|                          |                                     | - Option Elimination Analysis     |
|                          |                                     | - Epistemic Status Hanko Seal     |
+--------------------------+-------------------------------------+-----------------------------------+
```

### Key UI Features
1. **Editable Extracted Text:** If an image contains faded ink or an unusual handwriting glyph, users can click "Review / Edit Text", adjust the transcription directly in the UI, and click "Re-run Solver".
2. **Dynamic Model Selection:** Users can choose between local `qwen3.5:2b` or adaptive model routing.
3. **Synchronized Spatial Inspection:** Clicking a bounding box on the image canvas highlights the corresponding block in the sidebar and vice versa.
