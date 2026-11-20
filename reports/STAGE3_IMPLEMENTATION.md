# SETU-NETRA: Stage 3 Implementation Report
## Complete Document Question-Answering Vertical Slice

**System**: SETU-NETRA (Bridge-Eye)  
**Milestone**: Stage 3 — End-to-End Functional Delivery  
**Status**: Completed and Verified  
**Date**: November 2026  
**Test Suite Status**: 109 / 109 passing tests (0 failures, 0 errors, 14.08s execution time)

---

## 1. Executive Summary

Stage 3 transitions SETU-NETRA from a multi-stage document processing pipeline into a complete, working, evidence-grounded question-answering application. Prior milestones established raster preprocessing, OCR text extraction, geometry-based line grouping, dense-lexical hybrid retrieval, and SQLite persistence. 

Stage 3 bridges the gap between raw document representations and downstream question-answering by implementing:
1. **Multi-Format Document Ingestion**: Native zero-dependency extraction for Microsoft Word (`.docx`) and plain text (`.txt`), complete with synthetic preview canvases and spatial bounding boxes for visual provenance.
2. **Multi-Column Layout Disambiguation**: Recursive X-Y Cut algorithm for vertical whitespace gutter detection, eliminating cross-gutter text line merging in multi-column research papers and exam papers.
3. **Cognitive Question Understanding**: Structural and heuristic segmentation of single questions, multiple questions, and multiple-choice questions (MCQs), with automated cognitive intent classification (`DEFINITION`, `COMPARISON`, `CALCULATION`, `MECHANISM`, `MCQ_SELECTION`, `OPEN_ENDED`).
4. **Local CPU Inference Integration**: Standardized `InferenceRequest` and `InferenceResponse` contracts with model adapters (`GroundedExtractiveQAAdapter` and `LocalTransformersAdapter`) managed by a thread-safe `ModelRegistry`.
5. **Evidence-Grounded QA & Verification**: Tripartite verification taxonomy (`EVIDENCE_BACKED`, `GENERAL_KNOWLEDGE`, `UNSUPPORTED`) with exact citation matching `[Doc: <name>, Page: <p>, Block: <b>]` and token overlap scoring.
6. **Native Web Interface**: Zero-dependency interactive web application serving REST endpoints and a responsive UI with bounding-box canvas overlays and interactive question cards.

---

## 2. Phase-by-Phase Technical Implementation

### Phase 1: Multi-Format Document Ingestion
- **Implementation**: [`src/setu_netra/ingestion/validator.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ingestion/validator.py), [`src/setu_netra/ingestion/docx_loader.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ingestion/docx_loader.py), [`src/setu_netra/ingestion/text_loader.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ingestion/text_loader.py).
- **DOCX Ingestion**: Implemented native ZIP archive decompression and XML parsing (`word/document.xml`) without external dependencies. Paragraphs, headings (`w:pStyle`), and tables (`w:tbl`) are extracted. A synthetic 800x1100 PIL preview canvas is rendered with exact spatial coordinates assigned to each block.
- **TXT Ingestion**: Plain text files are parsed, line-wrapped, and paginated (40 lines/page default). Structural roles (`HEADING`, `QUESTION`, `PARAGRAPH`) are assigned heuristically, and preview canvases are synthesized.
- **Defensive Validation**: `validate_document_file` validates ZIP magic headers (`PK\x03\x04`), UTF-8 decodability, non-whitespace checks, and maximum size limits ($50\text{ MB}$).

### Phase 2: Multi-Column Layout Analysis (Recursive X-Y Cut)
- **Implementation**: [`src/setu_netra/structure/xy_cut.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/structure/xy_cut.py), [`src/setu_netra/structure/reconstructor.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/structure/reconstructor.py).
- **Theoretical Basis**: Based on Ha, Haralick, and Phillips (ICDAR 1995). Detects vertical whitespace gutters by projecting horizontal spans of bounding boxes onto the X-axis:
  $$\text{Projection}(x) = \sum_{i=1}^N \mathbb{I}(x_{\min}^{(i)} \le x \le x_{\max}^{(i)})$$
  Contiguous intervals where $\text{Projection}(x) = 0$ with $\text{width} \ge W_{\text{gutter}}$ ($25.0\text{ px}$) define column boundaries.
- **Integration**: `DocumentStructureReconstructor` groups detections column-by-column, preventing horizontal line merging across gutters. Paragraph block clustering is strictly maintained within each column's vertical flow.

### Phase 3: Question Extraction & Intent Classification
- **Implementation**: [`src/setu_netra/qa/question_extractor.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/question_extractor.py).
- **Segmentation**: Handles numbered questions (`Q1.`, `Question 1:`, `1.`), option patterns (`(A)`, `[B]`, `1.`), and multiline question text.
- **Taxonomy**: Classifies cognitive intents via pattern analysis:
  - `DEFINITION`: Prompts starting with *define*, *what is*, *what are*.
  - `COMPARISON`: Prompts containing *difference between*, *compare*, *distinguish*, *versus*.
  - `CALCULATION`: Prompts containing *calculate*, *compute*, *evaluate*, *find the value*.
  - `MECHANISM`: Prompts containing *how does*, *explain*, *describe*, *why does*.
  - `MCQ_SELECTION`: Questions containing $\ge 2$ structured options.
  - `OPEN_ENDED`: General prompts without specific lexical triggers.

### Phase 4: Local Model Integration & Unified Inference Interface
- **Implementation**: [`src/setu_netra/routing/contracts.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/contracts.py), [`src/setu_netra/routing/interfaces.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/interfaces.py), [`src/setu_netra/routing/registry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/registry.py), [`src/setu_netra/routing/adapters/grounded_qa_adapter.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/adapters/grounded_qa_adapter.py).
- **Standard Envelope**:
  $$\text{InferenceRequest}(\text{task\_type}, \text{prompt\_or\_payload}, \text{model\_id}, \text{request\_id}, \text{priority}, \text{timeout})$$
  $$\text{InferenceResponse}(\text{request\_id}, \text{result}, \text{executing\_model\_id}, \text{execution\_time}, \text{status}, \text{error\_info})$$
- **Grounded Extractive Adapter**: A local CPU engine that parses synthesized prompt blocks, extracts candidate answer sentences, binds exact citations, and enforces abstention when evidence is insufficient.
- **Registry**: Thread-safe model singleton managing discovery, task defaults, and hardware capability flags.

### Phase 5: Grounded Question Answering & Verification
- **Implementation**: [`src/setu_netra/qa/engine.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/engine.py), [`src/setu_netra/qa/verifier.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/verifier.py).
- **Workflow**:
  $$\text{Query} \xrightarrow{\text{Intent}} \text{Cleaned Query} \xrightarrow{\text{Hybrid Retrieve}} \text{Passages} \xrightarrow{\text{Budget Synthesizer}} \text{Context} \xrightarrow{\text{Model Adapter}} \text{Answer} \xrightarrow{\text{Verifier}} \text{VerifiedAnswer}$$
- **Verification Taxonomy**:
  - `EVIDENCE_BACKED`: All citations correspond to retrieved database passages, and token overlap ratio satisfies:
    $$\text{Overlap}(A, C) = \frac{|\mathcal{T}(A) \cap \mathcal{T}(C)|}{|\mathcal{T}(A)|} \ge 0.30$$
  - `GENERAL_KNOWLEDGE`: Answer contains no document citations and represents parametric knowledge.
  - `UNSUPPORTED`: Answer contains invalid/hallucinated citations or explicit model abstention.

### Phase 6: Native Web Application
- **Implementation**: [`src/setu_netra/ui/app.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ui/app.py).
- **Architecture**: Zero-external-dependency `ThreadingHTTPServer` running on port 8501.
- **Endpoints**:
  - `GET /`: Responsive HTML5/CSS3 application shell.
  - `POST /api/upload`: Multi-part document upload and ingestion.
  - `POST /api/query`: Evidence-grounded QA query processing.
  - `GET /api/document/<id>/questions`: Extracted question inspection.
  - `GET /api/document/<id>/page/<p>/image`: Dynamic page rendering with bounding-box highlights.

### Phase 7: Traffic & Scheduling Alignment
- Request envelopes include `request_id`, `priority`, `timeout`, and timestamps for drop-in compatibility with future Stage 4 adaptive routers and capacity-aware scheduling queues.

---

## 3. Architecture Overview

```mermaid
flowchart TD
    Doc[Multi-Format Upload\nPDF, DOCX, TXT, PNG] --> Val[Defensive Validator]
    Val --> Loader[Format Loader & Page Synthesis]
    Loader --> XY[Recursive X-Y Cut\nColumn Separation]
    XY --> Recon[Document Structure Reconstructor]
    Recon --> Store[(SQLite Document Store\nBlocks & Embeddings)]
    
    Q[User Question / Scanned Query] --> Ext[Question Extractor\nIntent & Option Parsing]
    Ext --> Ret[Document Retriever\nDense + Lexical Hybrid]
    Store --> Ret
    Ret --> Syn[Context Synthesizer\nToken Budget Enforcement]
    Syn --> Reg[Model Registry]
    Reg --> Model[Local Model Adapter\nCPU Execution]
    Model --> Ver[Citation Verifier\nGrounding & Epistemic Audit]
    Ver --> Out[Verified Answer\n[Doc, Page, Block] Bounding Boxes]
    Out --> UI[Web Interface & Canvas Highlights]
```

---

## 4. Source Artifacts Summary

| Component | File Path | Lines of Code | Key Classes / Functions |
| :--- | :--- | :--- | :--- |
| **DOCX Loader** | [`src/setu_netra/ingestion/docx_loader.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ingestion/docx_loader.py) | 196 | `load_docx_pages`, `parse_docx_xml` |
| **TXT Loader** | [`src/setu_netra/ingestion/text_loader.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ingestion/text_loader.py) | 106 | `load_text_pages` |
| **Recursive X-Y Cut** | [`src/setu_netra/structure/xy_cut.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/structure/xy_cut.py) | 192 | `detect_columns`, `_find_projection_valleys` |
| **Question Extractor** | [`src/setu_netra/qa/question_extractor.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/question_extractor.py) | 195 | `QuestionExtractor`, `classify_question_intent` |
| **Routing Contracts** | [`src/setu_netra/routing/contracts.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/contracts.py) | 102 | `InferenceRequest`, `InferenceResponse` |
| **Model Registry** | [`src/setu_netra/routing/registry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/registry.py) | 125 | `ModelRegistry`, `get_model_registry` |
| **Local QA Adapter** | [`src/setu_netra/routing/adapters/grounded_qa_adapter.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/adapters/grounded_qa_adapter.py) | 185 | `GroundedExtractiveQAAdapter` |
| **Citation Verifier** | [`src/setu_netra/qa/verifier.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/verifier.py) | 195 | `CitationVerifier`, `CitationVerificationResult` |
| **QA Engine** | [`src/setu_netra/qa/engine.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/engine.py) | 186 | `EvidenceGroundedQAEngine`, `VerifiedAnswer` |
| **Web Application** | [`src/setu_netra/ui/app.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/ui/app.py) | 509 | `SetuNetraHTTPHandler`, `start_server` |

---

## 5. Verification & Compliance Confirmation

- **Total Passing Tests**: **109** (all unit and integration tests passing).
- **Zero Regressions**: All 90 tests from Milestones 1–5 and Milestone 6 Sprint 1 continue passing with zero modification to core mathematical logic.
- **Zero Paid Cloud Dependencies**: Entire pipeline operates completely offline on local CPU hardware.
