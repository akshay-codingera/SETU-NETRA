# SETU-NETRA: Adaptive Neuro-Symbolic Framework for Document Understanding, Evidence Verification, and Context-Aware Reasoning

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-red)](https://pytorch.org/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-cyan)](frontend/)

SETU-NETRA is an academic, open-source neuro-symbolic document intelligence and question-answering framework. The architecture coordinates document layout extraction, spatial-relational edge modeling, neural evidence sufficiency verification, and context-managed reasoning policy execution for evidence-grounded information retrieval and answering on resource-constrained local hardware.

---

## Table of Contents
1. [Research Motivation & Problem Statement](#research-motivation--problem-statement)
2. [Research Objectives](#research-objectives)
3. [System Architecture](#system-architecture)
4. [Core Research Modules (R1–R4)](#core-research-modules-r1r4)
5. [Runtime Infrastructure & Application Stack](#runtime-infrastructure--application-stack)
6. [Technology Stack](#technology-stack)
7. [Installation & Setup](#installation--setup)
8. [Execution Instructions](#execution-instructions)
9. [Running Tests & Benchmarks](#running-tests--benchmarks)
10. [Current Implementation Status](#current-implementation-status)
11. [Known Limitations & Future Work](#known-limitations--future-work)
12. [Citation & Author Information](#citation--author-information)
13. [License](#license)

---

## Research Motivation & Problem Statement

Modern document question-answering systems frequently suffer from three interrelated deficiencies when deployed in real-world scenarios:
1. **Layout Fragmentation:** Complex visual structures (multi-column layouts, tables, headers, hierarchical forms, and handwritten annotations) lose semantic coherence when naively flattened into linear token sequences by conventional OCR tools.
2. **Hallucinatory Extrapolation & Unverifiability:** Large language models often hallucinate plausible-sounding answers when retrieved evidence is partial, conflicting, or fundamentally missing. Systems lack rigorous epistemic verification mechanisms to distinguish between sufficient evidence, contradictory statements, and unanswerable queries.
3. **Computational Resource Overhead:** Relying entirely on cloud-scale generative models introduces privacy vulnerabilities, high operational latency, and prohibitive memory consumption on local edge or workstation hardware.

SETU-NETRA addresses these challenges through an **adaptive neuro-symbolic framework** that pairs lightweight neural classifiers with deterministic domain solvers, governed by real-time hardware telemetry and epistemic confidence masks.

---

## Research Objectives

The SETU-NETRA framework accomplishes the following research goals:
- **Spatial Document Reconstruction:** Ingest diverse document formats (scanned images, multi-page PDFs, Word documents, raw text) and reconstruct 2D spatial relationships and reading order.
- **Relational Edge Understanding (R1):** Model structural dependencies between document blocks using geometric features and multi-modal node representations.
- **Evidence Verification (R2):** Score retrieved text passages across five epistemic classes: *Direct Entailment*, *Partial Support*, *Irrelevant Context*, *Contradiction*, and *Unverifiable Claim*.
- **Dynamic Policy Routing (R3):** Adaptively route queries across specialized deterministic solvers (Arithmetic, Relational DBMS, Formal Logic), extractive QA, or Small Language Models (SLM), enforcing an explicit *Abstain* option when evidence is insufficient.
- **Local-First Execution (R4):** Guarantee deterministic, bounded-latency processing on local CPU and workstation environments without requiring cloud GPU infrastructure.

---

## System Architecture

The overall pipeline executes in four structured stages:

```
[Document / Image Input]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ 1. Ingestion & Preprocessing (validator.py, loader.py) │
│    - File security & format verification               │
│    - EXIF auto-orientation, aspect resize, contrast    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Spatial-Relational Structure (R1: SR-EdgeNet)       │
│    - OCR extraction (EasyOCR / PyTesseract)            │
│    - Recursive XY-Cut & geometric bounding box graph  │
│    - Spatial-Relational Edge Network (sr_edge_net.pt) │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Evidence Verification (R2: ER-SP)                   │
│    - Neural passage-query cross-encoder (er_sp.pt)    │
│    - 5-Class epistemic scoring (Entailment/Conflict)   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 4. Context-Managed Reasoning Policy (R3: CM-RP)        │
│    - Hardware feasibility mask (RAM/CPU telemetry)     │
│    - 7-Action solver dispatch (cm_rp.pt / cm_rp_v2.pt) │
│    - Solvers: Arithmetic | DBMS | Logic | Extractive   │
│               Local SLM | Multi-Hop | ABSTAIN          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
               [Grounded Structured Response]
```

---

## Core Research Modules (R1–R4)

### R1: Spatial-Relational Edge Network (SR-EdgeNet)
- **Path:** `src/setu_netra/structure/sr_edge_net.py`
- **Trained Model Checkpoint:** `models/structure/sr_edge_net.pt`
- **Functionality:** Operates on document graph nodes constructed from bounding box geometry and text embeddings. Predicts relational edge categories (Sequential Flow, Parent-Child Hierarchies, Table Association, Cross-Column Grouping).
- **Data Provenance:** Evaluated on 459 document entities (47,557 edges) across synthetic document layouts and gold-standard benchmarks (FUNSD dataset).

### R2: Evidence Relevance & Sufficiency Predictor (ER-SP)
- **Path:** `src/setu_netra/evidence/er_sp.py`
- **Trained Model Checkpoint:** `models/evidence/er_sp.pt`
- **Functionality:** Lightweight neural scorer that computes joint embeddings of query intentions and retrieved document chunks to produce a 5-class distribution:
  1. `DIRECT_ENTAILMENT`: Retrieved evidence directly answers the prompt.
  2. `PARTIAL_SUPPORT`: Incomplete context requiring multi-hop retrieval.
  3. `IRRELEVANT`: Document does not contain relevant topical semantics.
  4. `CONTRADICTORY`: Retrieved context contains conflicting assertions.
  5. `UNVERIFIABLE`: External knowledge claim absent from source document.

### R3: Context-Managed Reasoning Policy (CM-RP)
- **Path:** `src/setu_netra/policy/cm_rp.py`
- **Trained Model Checkpoints:** `models/policy/cm_rp.pt` (v1) and `models/policy/cm_rp_v2.pt` (v2)
- **Functionality:** Multilayer perceptron policy network that inspects query semantics, ER-SP evidence distribution, and real-time host telemetry.
- **Hardware Feasibility Mask:** Active gating (`cm_rp.py:211`) dynamically suppresses heavy SLM generation if available system RAM falls below 1,500 MB or memory pressure exceeds 90%.
- **Action Space (7 Actions):**
  - `ARITHMETIC_SOLVER`: Deterministic mathematical equation solver.
  - `DBMS_SOLVER`: Structured relational query engine.
  - `FORMAL_LOGIC_SOLVER`: First-order / propositional inference engine.
  - `EXTRACTIVE_QA`: Direct span extraction from verified document evidence.
  - `LOCAL_SLM`: Small Language Model generation when evidence is non-trivial.
  - `ADDITIONAL_RETRIEVAL`: Multi-hop recursive search trigger.
  - `ABSTAIN`: Explicit safety fallback when evidence is insufficient or contradictory.

### R4: Full-System Integration Pipeline
- **Path:** `src/setu_netra/pipeline/integrated_pipeline.py`
- **Functionality:** Unifies ingestion, OCR extraction, SR-EdgeNet structure parsing, ER-SP validation, and CM-RP solver routing into a single deterministic execution harness with full telemetry instrumentation.

---

## Runtime Infrastructure & Application Stack

In addition to the primary research models, SETU-NETRA includes a full multi-user production runtime:
- **FastAPI Backend (`src/setu_netra/api/`):** REST API endpoints providing document ingestion, background task processing, session-based querying, workspace isolation, and live telemetry feeds.
- **Role-Based Security (`src/setu_netra/auth/`):** RBAC authorization, password hashing, session tokens, audit logging, and rate limiting.
- **Storage Subsystem (`src/setu_netra/store/`):** SQLite persistence engine with schema version migrations and ACID transaction guarantees.
- **Fault Tolerance & Reliability (`src/setu_netra/routing/fault_tolerance.py`):** Three-state Circuit Breaker (Closed, Open, Half-Open), bounded SLA timeouts, and idempotency-aware retry policies.
- **Dynamic Scheduler (`src/setu_netra/routing/dynamic_scheduler.py`):** Multi-workload request scheduler supporting FIFO, Priority, Shortest-Job-First, and Adaptive Resource Scheduling (ARS).
- **Modern Web UI (`frontend/`):** Production React 18 + TypeScript + Vite + TailwindCSS client featuring document visualization, query consoles, and system telemetry dashboards.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Deep Learning & NLP** | PyTorch, Hugging Face Transformers, Sentence-Transformers (`all-MiniLM-L6-v2`) |
| **Vision & OCR** | OpenCV, EasyOCR, PyTesseract, Pillow, PyMuPDF |
| **Backend & API** | Python 3.10+, FastAPI, Starlette, Uvicorn, Pydantic v2 |
| **Data & Storage** | SQLite3, SQLAlchemy, NumPy, SciPy, Scikit-learn |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Lucide Icons |
| **Benchmarking & Testing**| PyTest, Unittest, Psutil, AsyncIO |

---

## Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12 (tested on Windows 11 and Ubuntu Linux)
- Node.js 18+ and npm (for frontend dashboard)
- Git (and optionally Git LFS)

### 1. Clone the Repository
```bash
git clone https://github.com/akshay-codingera/SETU-NETRA.git
cd SETU-NETRA
```

### 2. Configure Python Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Build Frontend (Optional for Web Dashboard)
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## Execution Instructions

### Run the FastAPI Backend Server
```bash
uvicorn setu_netra.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### Run Single-Image Document Processing CLI
```bash
python run_milestone1.py --image sample_data/sample_question.png
```

### Run Frontend Development Server
```bash
cd frontend
npm run dev
```

---

## Running Tests & Benchmarks

### Execute Core Test Suite
```bash
python -m unittest discover -s tests
```

### Run End-to-End Pipeline Verification
```bash
python runtime_verification_phase1.py
python runtime_verification_phase2.py
```

### Run Comprehensive Research Benchmark Suite
All experimental logs, ablation scripts, and reconciliation benchmarks are located in:
- `benchmarks/` — Automated scheduler, reliability, and OCR performance suites.
- `research_audit/evidence_reconciliation_20261120/` — Cryptographically verified research reconciliation package and source-to-claim matrices.

---

## Current Implementation Status

| Subsystem / Capability | Status | Implementation Details |
| :--- | :---: | :--- |
| **Image Ingestion & Formats** | **Complete** | PDF, PNG, JPEG, DOCX, TXT loaders with security headers and EXIF correction. |
| **OCR & Layout Processing** | **Complete** | Dual EasyOCR and Tesseract backends with reading-order reconstruction. |
| **SR-EdgeNet (R1)** | **Complete** | Trained model checkpoint in `models/structure/sr_edge_net.pt`. |
| **ER-SP Scorer (R2)** | **Complete** | 5-class neural sufficiency classifier in `models/evidence/er_sp.pt`. |
| **CM-RP Policy (R3)** | **Complete** | 7-action policy in `models/policy/cm_rp_v2.pt` with active RAM gating. |
| **Domain Solvers** | **Complete** | Arithmetic, DBMS, Formal Logic, and Extractive QA operational. |
| **Full Pipeline (R4)** | **Complete** | Integrated execution engine with fallback cascades. |
| **FastAPI REST API** | **Complete** | Complete routers for Auth, Documents, Query, Workspaces, and Telemetry. |
| **React Web Frontend** | **Complete** | Multi-page modern user interface in `frontend/`. |

---

## Known Limitations & Future Work

- **OCR Speed on CPU:** Heavy multi-page documents processed through EasyOCR on CPU exhibit latencies (~4.5s/page). Integration of quantized ONNX runtimes is planned.
- **Complex Table Parsing:** Highly irregular borderless nested tables currently require fallback to XY-Cut geometric heuristic splitting.
- **Fine-Grained Formal Logic:** While propositional and first-order syllogisms are handled natively, complex multi-hop temporal logic chains remain an active research avenue.

---

## Citation & Author Information

**Author:** Akshay Butola  
**GitHub:** [@akshay-codingera](https://github.com/akshay-codingera)  
**Email:** akshaybutola2005@gmail.com  

If you use SETU-NETRA in your work, please cite:

```bibtex
@software{butola2026setunetra,
  author = {Butola, Akshay},
  title = {SETU-NETRA: Adaptive Neuro-Symbolic Framework for Document Understanding, Evidence Sufficiency Assessment, and Context-Aware Reasoning},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/akshay-codingera/SETU-NETRA}}
}
```

---

## License

This project is licensed under the **Apache License 2.0** — see the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details. Third-party libraries and datasets are recognized under their respective original licenses in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
