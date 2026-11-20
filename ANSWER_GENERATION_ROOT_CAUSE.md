# SETU-NETRA V2.0.0-RC1 — ROOT CAUSE ANALYSIS REPORT
## Defect: Question Identification Without Answer Generation (Repetition & Epistemic Rejection)

**Target Invariant:** Uploaded image or queried question must produce a verified, computed/reasoned answer rather than echoing the prompt with an `UNSUPPORTED (Insufficient evidence)` verdict.  
**Severity:** Critical Architectural Defect  
**Status:** Diagnosed, Fully Root-Caused, Repaired, and Empirically Verified.

---

### 1. Executive Summary

When a user uploaded a handwritten or printed arithmetic problem (specifically `quest6.png`: `Given : a = 10 ; b = 5 ; result = a + b - 23 + 40 ; What is the Value of result?`), SETU-NETRA extracted the OCR text accurately but generated the following output:
- **Epistemic Outcome:** `UNSUPPORTED (Insufficient evidence)`
- **Synthesized Answer:** Echo of the extracted question (`Question Given : a = 10 ; b = 5 ; result = a+b - 23 + 40 ; What is the Value of result [Doc: quest6.png, Page: 1, Block: 1]`)
- **Citations Card:** `""` (Empty string citation marked as `Score: Verified`)
- **Computed Value:** None (Calculated result `32` was completely missing).

This report details the end-to-end trace, the three contributing architectural traps, and how each has been dismantled.

---

### 2. End-to-End Request Pipeline Failure Trace

The failure was traced across the 8 lifecycle stages:

```
[Uploaded Image: quest6.png]
       │
       ▼ (1) EasyOCR Text Detection
       │ Extracted: "Question_\nGiven :\na = 10 ; b = 5 ;\nresult = a+b _ 23 + 40 ;\nWhot is the Value of result"
       ▼ (2) Document Structure & Storage
       │ Saved into SQLite `document_blocks` as Block #1 (Confidence: 0.8136)
       ▼ (3) User Action: "Identify and Answer Question" / Intelligence QA Query
       │ User clicked "IDENTIFY AND ANSWER QUESTION" or queried "What is the Value of result?"
       ▼ (4) Extractive RAG Mis-Routing Trap
       │ HybridRetriever matched query to Block #1 of quest6.png (relevance 0.81).
       │ Context Synthesizer injected Block #1 into the extractive LLM prompt:
       │ "Answer the query strictly based on the provided document passages..."
       ▼ (5) Extractive Model Copy Trap
       │ The model observed that the document contained ONLY the problem statement.
       │ Strictly obeying the extractive prompt instruction, the model copied the text of Block #1
       │ and appended "[Doc: quest6.png, Page: 1, Block: 1]".
       ▼ (6) Citation Verification Breakdown
       │ CitationVerifier attempted lexical overlap against Block #1.
       │ The synthesized text matched the question verbatim, but factual answer claim extraction failed.
       │ Verifier marked the claim as unsupported due to lack of an external source asserting "result = 32".
       ▼ (7) Empty Citation UI Glitch
       │ An empty citation record `""` was assigned a verified status due to a fallback default,
       │ rendering an empty card on the canvas with "Score: Verified".
       ▼ (8) Final Output
         Status: UNSUPPORTED (Insufficient evidence)
         Synthesized Answer: Verbatim question text
         Actual Calculation (32): Lost.
```

---

### 3. Detailed Breakdown of Contributing Root Causes

#### A. The Epistemic Category Error: Inductive Retrieval vs. Deductive Computation
The fundamental architectural flaw was treating **all inquiries as inductive document retrieval problems**.
- Document QA is **inductive and evidence-grounded**: It retrieves external empirical facts (e.g., "Who signed the Treaty of Versailles?"). An assertion is only valid if a cited document explicitly contains the claim.
- Arithmetic and Mathematics are **deductive and computational**: `10 + 5 - 23 + 40` does not rely on an external document stating that the answer is 32. It relies on deterministic mathematical rules (Peano axioms, operator precedence, AST reduction).
- Forcing a self-contained arithmetic question into an extractive RAG pipeline created an impossible condition: the document was an inquiry sheet, so it *did not contain* the answer. Demanding that the model cite evidence for the answer guaranteed an `UNSUPPORTED` verdict.

#### B. The Extractive Prompt Trap
The default generation prompt instructed the model:
`"Answer the question using only the provided context. If the answer cannot be found in the context, do not assume."`
When fed a question image, the model correctly identified that the context *was* the question. Unable to find a pre-existing answer sentence in the text, it reproduced the problem statement verbatim and cited the block where it found it.

#### C. OCR Glyphs & Noisy Character Artifacts
Handwritten images introduce specific character confusions that break standard mathematical tokenizers:
1. **The Underscore Minus Confusion:** In `quest6.png`, the handwritten minus sign `-` was recognized by EasyOCR as an underscore `_`:
   `result = a+b _ 23 + 40`
2. **Alphanumeric Collisions:**
   - `IO` or `lo` instead of `10`
   - `4O` instead of `40`
   - `whot` instead of `what`
3. **Regex Collision Bug:**
   In early regex parsing, `\b([a-z_][a-z0-9_]*)\s*[=2:]\s*([0-9]+)` treated `_` as a valid variable name, and `2` in `23` as an equals sign (`=`), parsing `_ 23` as variable `_ = 3`. Substituting `_` with `3` produced the corrupted formula `10+5 3 23 + 40`, which threw an AST syntax error and aborted the calculation.

#### D. Fabricated / Empty Citations in Arithmetic
Because the citation pipeline expected every answer to reference a bounding box, previous logic returned dummy citations with empty text strings `""` when evaluating equations. This led to the confusing UI card showing `Score: Verified` next to blank quotes.

---

### 4. Corrective Architecture Implemented

1. **Pre-Retrieval Domain Classification:** Queries and ingested page text are analyzed by `DomainSolverRouter` before being sent to extractive RAG.
2. **Safe Deterministic AST Evaluator:** Pure arithmetic expressions are evaluated directly using Python's `ast` parser (supporting $+$, $-$, $*$, $/$, parentheses, negative numbers, and decimals) without unrestricted `eval()`.
3. **Context-Aware OCR Normalization:** `normalize_ocr_arithmetic_tokens` converts OCR artifacts (`IO` $\to$ `10`, `4O` $\to$ `40`, `_` in arithmetic contexts $\to$ `-`, `whot` $\to$ `what`) before parsing, while preserving raw OCR text.
4. **Epistemic Status Separation:** Computations receive `COMPUTATION_VERIFIED` with `citations = []` and a step-by-step derivation proof, eliminating fake citations.
5. **Frontend Dual Presentation:** In `QuestionAnsweringView.tsx` and `DocumentIntelligenceView.tsx`, verified answers are rendered with bold prominence, accompanied by step-by-step reasoning steps and suppression of blank citations.
