# SETU-NETRA: Existing System Baseline Technical Audit

**Report ID:** SETU-AUDIT-BASE-001  
**Date:** November 9, 2026  
**Audited Baseline:** Milestones 1–5 + Milestone 6 Sprint 1  
**Status:** Empirically Verified via Codebase Inspection and 90 Automated Tests  
**Target Environment:** Local Windows 11 (Intel Core i5-1334U, 16 GB RAM, CPU-only PyTorch)  

---

## 1. Executive Summary

SETU-NETRA began as an academic proof-of-concept for document intelligence. Through Milestones 1–5 and Milestone 6 Sprint 1, it evolved into an integrated, evidence-backed document ingestion, OCR, layout reconstruction, semantic embedding, SQLite persistence, and hybrid retrieval pipeline.

This audit establishes the ground-truth technical state of the repository before extending it with adaptive AI model routing and intelligent inference traffic management.

### Baseline Summary Metrics
* **Automated Tests:** **90 tests** passing in $\approx 29.89\text{s}$ (`$env:PYTHONPATH="src"; .venv\Scripts\python -m unittest discover -s tests`).
* **Active Neural Models:**
  - `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense embeddings; 22.7M parameters; locally cached).
  - EasyOCR text detection: CRAFT (Character Region Awareness for Text Detection; fully convolutional VGG backbone).
  - EasyOCR text recognition: CRNN + CTC (CNN feature extractor + BiLSTM/BiGRU sequence modeling + CTC alignment).
* **Active Deterministic Fallback:**
  - `OfflineSemanticEngine` (512-dimensional subword character n-gram hashing and 12 canonical academic synsets).
* **Storage Engine:** SQLite 3 with Write-Ahead Logging (`WAL`), `synchronous = NORMAL`, and foreign-key referential integrity.
* **Retrieval Subsystem:** Dual-channel hybrid search combining rectified dense cosine similarity ($q \cdot M^T$) with bag-of-words lexical overlap, bounded in $[0.0, 1.0]$, augmented with near-duplicate and repeated header suppression.

---

## 2. Implemented Subsystems & Source Inventory

```
src/setu_netra/
├── core/
│   └── contracts.py               # Immutable dataclasses: OCRBox, OCRResult, DocumentStructureResult,
│                                  # StoredDocument, RetrievedPassage, SynthesizedContext
├── ingestion/
│   ├── validator.py               # File format validation, 50MB ceiling, %PDF magic-byte checks
│   ├── loader.py                  # Raster image loading, EXIF auto-orientation, metadata extraction
│   └── pdf_loader.py              # PDFium (pypdfium2) streaming decomposition at 150 DPI
├── preprocessing/
│   ├── operations.py              # In-memory ITU-R 601 grayscale (0.299R+0.587G+0.114B), contrast scaling
│   └── pipeline.py                # Preprocessing pipeline orchestration
├── ocr/
│   ├── base.py                    # BaseOCREngine abstract base class
│   ├── easyocr_engine.py          # Real deep-learning OCR adapter (CRAFT + CRNN)
│   ├── mock_engine.py             # Deterministic synthetic test fixture
│   └── factory.py                 # OCREngineFactory with lazy loading
├── structure/
│   ├── line_grouper.py            # Geometric line grouping with adaptive overlap > 0.50
│   ├── block_grouper.py           # Inter-line vertical spacing clustering
│   ├── classifier.py              # Rule-based structural tagging: HEADING, QUESTION, OPTION, PARAGRAPH
│   └── reconstructor.py           # MCQ option-to-question spatial association & hierarchy assembly
├── semantic/
│   ├── embeddings/
│   │   ├── base.py                # BaseEmbeddingEngine abstract contract
│   │   ├── neural_engine.py       # all-MiniLM-L6-v2 sentence transformer adapter
│   │   ├── offline_engine.py      # 512-dim subword feature hashing baseline
│   │   └── factory.py             # EmbeddingEngineFactory with auto-selection
│   ├── domain/
│   │   ├── taxonomy.py            # 12-domain academic taxonomy (CS, Math, Physics, etc.)
│   │   ├── classifier.py          # Open-vocabulary cosine similarity domain classifier
│   │   └── disambiguation.py      # Contextual disambiguation rules (e.g. OS kernel vs ML kernel)
│   └── retrieval/
│       └── local_knowledge.py     # Legacy static educational reference tuples (superseded)
├── store/
│   └── sqlite_store.py            # Persistent SQLite database: documents, pages, document_blocks,
│                                  # defensive BLOB unpacking, SHA-256 deduplication
├── retrieval/
│   └── document_retriever.py      # Hybrid dense/lexical search, ReLU dense rectification,
│                                  # near-duplicate & repeated header suppression
└── context/
    └── synthesizer.py             # Token-budgeted context formatting with strict citation tags
```

---

## 3. Subsystem-by-Subsystem Technical Audit

### M1: Document Ingestion & Validation
* **Status:** Fully functional.
* **Capabilities:** Handles `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.webp`. Enforces a 50MB file size ceiling and checks `%PDF` magic bytes for PDF files. Rasterizes multi-page PDFs using `pypdfium2` at 150 DPI into sequential PIL Image buffers while preserving 1-based page numbering.
* **Limitations:** Does not yet support Microsoft Word (`.docx`), plain text (`.txt`), or rich document formats (`.pptx`).

### M2: OCR & Text Extraction
* **Status:** Fully functional on CPU.
* **Capabilities:** `EasyOCREngine` runs deep-learning CRAFT text detection and CRNN character recognition. Produces quadrilateral bounding polygons, text transcripts, and character confidence scores.
* **Limitations:** Hardcoded to English (`lang_list=['en']`). Visual orientation detection is absent; 90-degree rotated scans fail text recognition. CPU execution requires $\approx 2.8\text{ seconds per page}$.

### M3: Document Structure Reconstruction
* **Status:** Fully functional for single-column layouts and academic MCQ exams.
* **Capabilities:** Sorts OCR bounding boxes top-to-bottom and left-to-right. Clusters overlapping words into lines and lines into blocks based on inter-line spacing. Identifies headings, questions, options (A, B, C, D / 1, 2, 3, 4), and associates options with preceding questions.
* **Limitations:** Lacks multi-column spatial decomposition (XY-Cut). Lines spanning across column gutters are merged horizontally if their vertical coordinates overlap. Tables are flattened into loose paragraph blocks.

### M4: Semantic Understanding & Embeddings
* **Status:** Fully functional dual-engine backend.
* **Capabilities:** `NeuralSentenceEmbeddingEngine` computes 384-dimensional $L_2$-normalized dense embeddings using `all-MiniLM-L6-v2`. `OfflineSemanticEngine` provides deterministic 512-dimensional subword hashing. Domain classification supports 12 academic fields with cosine thresholding and contextual disambiguation.
* **Limitations:** No generation or reasoning capabilities. The semantic engine classifies domains and embeds text, but cannot synthesize answers on its own.

### M5: Persistent Storage & Hybrid Retrieval
* **Status:** Fully functional and hardened.
* **Capabilities:** `SQLiteDocumentStore` stores file metadata, SHA-256 hashes, page geometry, structural blocks, and raw float32 vector BLOBs with WAL mode. `DocumentRetriever` combines dense cosine dot-products with lexical keyword overlap.
* **Hardening in M6 Sprint 1:** Truncated and malformed BLOBs are defensively skipped without crashing. Negative cosine scores are rectified via ReLU ($\max(0.0, S_{\text{dense}})$) to prevent dragging down lexical keyword matches. Near-duplicate blocks and repeated headers across pages are filtered out of top-$K$ results.
* **Limitations:** Vectors are loaded sequentially from SQLite on each search call. While sub-millisecond for corpora $< 10{,}000$ blocks, an in-memory vector cache or specialized vector index (e.g. HNSW / FAISS / SQLite-vec) is needed for very large repositories.

---

## 4. Test Suite Audit & Verification

The automated test suite was executed in PowerShell on the live repository:
```text
$env:PYTHONPATH="src"; .venv\Scripts\python -m unittest discover -s tests

Ran 90 tests in 29.890s

OK
```

### Breakdown of Passing Test Modules:
1. `tests/test_ingestion.py` (9 tests): File validation, headers, luma grayscale, contrast, and resize transforms.
2. `tests/test_ocr.py` (8 tests): Engine contracts, geometry calculations, confidence filtering, and mock engine.
3. `tests/test_structure.py` (10 tests): Line grouping, block clustering, MCQ option association, reading order, and malformed coordinates.
4. `tests/test_semantic.py` (24 tests): Offline subword hashing, neural weight loading, domain taxonomy, contextual disambiguation, and JSON serialization.
5. `tests/test_milestone5.py` (7 tests): PDF decomposition, process restart persistence, SHA-256 deduplication, multi-document retrieval, token budgeting, and end-to-end pipeline.
6. `tests/test_embedding_corruption.py` (6 tests): Truncated BLOBs, empty buffers, dimension mismatches, non-finite values (NaN/Inf), and mixed database recovery.
7. `tests/test_hybrid_score_robustness.py` (8 tests): ReLU rectification, negative cosine drag elimination, pure dense/lexical modes, and empty queries.
8. `tests/test_duplicate_suppression.py` (7 tests): Repeated headers, exact duplicate blocks, near-duplicate typos, question preservation, and cross-document duplicates.

---

## 5. Architectural Boundaries & Starting Point for Routing

Currently, SETU-NETRA operates as a **linear, deterministic pipeline**:
$$\text{File Ingestion} \longrightarrow \text{OCR} \longrightarrow \text{Structure} \longrightarrow \text{Embeddings} \longrightarrow \text{SQLite} \longrightarrow \text{Hybrid Retrieval} \longrightarrow \text{Prompt Synthesizer}$$

The system lacks:
1. **Generative Language Model Execution:** `synthesizer.py` formats prompt strings with evidence citations, but does not execute inference against an LLM/SLM.
2. **Model Selection & Registry:** There is no centralized registry cataloging models across tasks (OCR, embedding, extraction, summarization, reasoning, answering) with capability and cost profiles.
3. **Traffic Management & Worker Queues:** All processing occurs synchronously in the caller's thread without queueing, worker pools, concurrency limits, or capacity-aware load balancing.
4. **Adaptive Cascading:** The pipeline cannot dynamically escalate a query from a lightweight local model to a more powerful model based on confidence or complexity.

These four gaps form the direct motivation and mandate for the second major direction of the CSE minor project: **Adaptive Model Routing and Intelligent AI Traffic Management**.
