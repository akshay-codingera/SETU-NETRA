# SETU-NETRA: Engineering Implementation Roadmap & Milestone Schedule
## 10-Stage Phased Execution Plan for the CSE Minor Project

**Report ID:** SETU-ROADMAP-009  
**Date:** November 9, 2026  
**Audience:** Project Supervisor, Evaluators, Engineering Team  

---

## 1. Executive Roadmap Overview

To ensure academic rigor, software reliability, and verifiable reproducibility, SETU-NETRA is developed in **10 decoupled, sequentially gated stages**. Each stage delivers concrete source code, comprehensive automated tests, documentation, and empirical measurements before progressing to the next tier.

```mermaid
flowchart LR
    S1["Stage 1:\nAudit & Lit Review\n(DONE)"] --> S2["Stage 2:\nArchitecture & Specs\n(DONE)"]
    S2 --> S3["Stage 3:\nDoc QA Vertical Slice"]
    S3 --> S4["Stage 4:\nModel Registry & Interface"]
    S4 --> S5["Stage 5:\nLocal Worker Pool"]
    S5 --> S6["Stage 6:\nBaseline Schedulers\n(RR, Random, LOR)"]
    S6 --> S7["Stage 7:\nCapacity-Aware Schedulers\n(SECT, CAS, ARS)"]
    S7 --> S8["Stage 8:\nModel Cascading & Grounding"]
    S8 --> S9["Stage 9:\nUnified UI & Dashboards"]
    S9 --> S10["Stage 10:\nFull System Benchmark"]
```

---

## 2. Stage-by-Stage Implementation Breakdown

### Stage 1: Repository Audit & Literature Review (COMPLETED)
* **Objective:** Establish the factual baseline of the existing codebase and survey research across model routing, traffic scheduling, and document intelligence.
* **Deliverables:**
  - [`reports/EXISTING_SYSTEM_AUDIT.md`](file:///d:/Projects/Setu-Netra/reports/EXISTING_SYSTEM_AUDIT.md)
  - [`reports/RESEARCH_LITERATURE_REVIEW.md`](file:///d:/Projects/Setu-Netra/reports/RESEARCH_LITERATURE_REVIEW.md)
  - [`reports/HARDWARE_AND_MODEL_FEASIBILITY.md`](file:///d:/Projects/Setu-Netra/reports/HARDWARE_AND_MODEL_FEASIBILITY.md)
  - [`reports/RESEARCH_CONTRIBUTION.md`](file:///d:/Projects/Setu-Netra/reports/RESEARCH_CONTRIBUTION.md)
* **Gate Check:** 90 passing baseline unit tests; verified local hardware specifications (i5-1334U, 16 GB RAM).

---

### Stage 2: Unified Architecture & Technical Specification (COMPLETED)
* **Objective:** Produce comprehensive architectural designs integrating Document Intelligence, Model Routing, and Traffic Management.
* **Deliverables:**
  - [`reports/DOCUMENT_INTELLIGENCE_ARCHITECTURE.md`](file:///d:/Projects/Setu-Netra/reports/DOCUMENT_INTELLIGENCE_ARCHITECTURE.md)
  - [`reports/MODEL_ROUTING_DESIGN.md`](file:///d:/Projects/Setu-Netra/reports/MODEL_ROUTING_DESIGN.md)
  - [`reports/TRAFFIC_SCHEDULING_DESIGN.md`](file:///d:/Projects/Setu-Netra/reports/TRAFFIC_SCHEDULING_DESIGN.md)
  - [`reports/UNIFIED_SYSTEM_ARCHITECTURE.md`](file:///d:/Projects/Setu-Netra/reports/UNIFIED_SYSTEM_ARCHITECTURE.md)
  - [`reports/IMPLEMENTATION_ROADMAP.md`](file:///d:/Projects/Setu-Netra/reports/IMPLEMENTATION_ROADMAP.md)
  - [`reports/BENCHMARKING_METHODOLOGY.md`](file:///d:/Projects/Setu-Netra/reports/BENCHMARKING_METHODOLOGY.md)
* **Gate Check:** Formal sign-off on contracts, schemas, and mathematical formulations.

---

### Stage 3: Complete Document Question-Answering Vertical Slice
* **Objective:** Build an end-to-end working pipeline that accepts a document, performs OCR and structural reconstruction, and answers queries with verified citations.
* **Source Modules to Implement / Extend:**
  - `src/setu_netra/ingestion/docx_loader.py` (DOCX ingestion via `python-docx`).
  - `src/setu_netra/structure/xy_cut.py` (Recursive XY-Cut layout segmentation).
  - `src/setu_netra/qa/engine.py` (Grounded Question-Answering engine).
  - `src/setu_netra/qa/verifier.py` (Citation overlap & hallucination checker).
* **Test Suite:** `tests/test_document_qa_slice.py` (Testing end-to-end ingestion $\to$ answer generation $\to$ citation verification).
* **Acceptance Criteria:** Given a multi-page PDF or image, answer user queries with $100\%$ accurate citation tags `[Doc, Page, Block]` matching SQLite coordinates.

---

### Stage 4: Model Registry & Unified Inference Interface
* **Objective:** Implement the decoupled model catalog and abstract inference contract.
* **Source Modules to Implement:**
  - `src/setu_netra/routing/registry.py` (`ModelProfile`, `ModelRegistry` catalog).
  - `src/setu_netra/routing/interfaces.py` (`UnifiedModelInterface`).
  - `src/setu_netra/routing/adapters/` (Local PyTorch adapter, GGUF/llama.cpp adapter, HuggingFace adapter, Mock adapter).
* **Test Suite:** `tests/test_model_registry.py` (Testing model registration, task filtering, profile retrieval, and adapter execution).
* **Acceptance Criteria:** Multiple models can be invoked through the identical `execute()` signature; incompatible tasks are safely rejected.

---

### Stage 5: Multiple Local Inference Workers
* **Objective:** Implement an asynchronous worker pool with thread/subprocess isolation and live telemetry monitoring.
* **Source Modules to Implement:**
  - `src/setu_netra/traffic/worker.py` (`InferenceWorker` state machine: `IDLE`, `BUSY`, `UNHEALTHY`).
  - `src/setu_netra/traffic/pool.py` (`WorkerPool` manager, dynamic scaling).
  - `src/setu_netra/traffic/telemetry.py` (Process CPU, RSS memory, EMA latency tracking).
* **Test Suite:** `tests/test_worker_pool.py` (Testing worker spawning, heartbeat health probes, task execution, and crash recovery).
* **Acceptance Criteria:** Spawning 3 concurrent workers maintains $< 500\text{ MB}$ base memory footprint and reports live telemetry without race conditions.

---

### Stage 6: Baseline Scheduling Algorithms (RR, Random, LOR)
* **Objective:** Implement foundational load-balancing strategies.
* **Source Modules to Implement:**
  - `src/setu_netra/traffic/schedulers/base.py` (`BaseScheduler` abstract interface).
  - `src/setu_netra/traffic/schedulers/round_robin.py` (`RoundRobinScheduler`).
  - `src/setu_netra/traffic/schedulers/random_scheduler.py` (`RandomScheduler`).
  - `src/setu_netra/traffic/schedulers/least_outstanding.py` (`LeastOutstandingRequestsScheduler`).
* **Test Suite:** `tests/test_baseline_schedulers.py` (Simulated multi-request workloads verifying uniform and queue-weighted distribution).
* **Acceptance Criteria:** Schedulers execute dispatch decisions in $< 0.1\text{ ms}$; LOR provably balances queue depth.

---

### Stage 7: Adaptive & Capacity-Aware Scheduling (SECT, CAS, ARS)
* **Objective:** Implement advanced telemetry-driven scheduling.
* **Source Modules to Implement:**
  - `src/setu_netra/traffic/schedulers/sect.py` (Shortest Estimated Completion Time).
  - `src/setu_netra/traffic/schedulers/capacity_aware.py` (Hardware telemetry capacity scoring & backpressure).
  - `src/setu_netra/traffic/schedulers/adaptive.py` (Error-rate and degradation penalized routing).
* **Test Suite:** `tests/test_adaptive_schedulers.py` (Testing performance under simulated CPU spikes, memory starvation, and worker failures).
* **Acceptance Criteria:** Under $90\%$ simulated load, CAS triggers backpressure; ARS automatically routes traffic away from failing workers.

---

### Stage 8: Quality-Aware Model Selection & Cascading
* **Objective:** Implement multi-tier model escalation based on answer verification.
* **Source Modules to Implement:**
  - `src/setu_netra/routing/classifier.py` (Query complexity and token length classifier).
  - `src/setu_netra/routing/cascade.py` (`ModelCascadeController`).
* **Test Suite:** `tests/test_model_cascading.py` (Testing early exit on high confidence vs. escalation on missing citations).
* **Acceptance Criteria:** Simple queries resolve on Tier 1 SLM; ambiguous/unsupported queries escalate to Tier 2 without user intervention.

---

### Stage 9: Integrated Monitoring Dashboard & Web Workspaces
* **Objective:** Build the interactive user interface with dual workspaces.
* **Technology:** Streamlit / FastAPI + React (lightweight, highly responsive on Windows).
* **Workspaces:**
  - **Workspace 1 (Document Intelligence):** Document upload, visual PDF viewer with bounding-box overlays, extracted Q&A cards, and verified answer generator.
  - **Workspace 2 (AI Orchestration Dashboard):** Live worker telemetry gauges (CPU, RAM, queue depth), active scheduler toggle, real-time latency percentiles, and cascading decision logs.
* **Test Suite:** `tests/test_api_endpoints.py` (Testing REST/UI endpoints).
* **Acceptance Criteria:** Real-time metrics refresh every 1000ms with zero latency impact on active worker inferences.

---

### Stage 10: Full System Integration & Benchmarking
* **Objective:** Execute the complete comparative benchmark across identical workloads and publish the final evaluation report.
* **Deliverables:**
  - `reports/FINAL_MINOR_PROJECT_EVALUATION.md`
  - Automated benchmark harness (`benchmarks/run_traffic_benchmark.py`).
  - Empirical graphs: Throughput (RPS), p50/p95/p99 Latency, Worker Utilization, and Cascading Cost-Savings.
* **Acceptance Criteria:** Fully reproducible benchmark script verifying Hypotheses $H_1, H_2, H_3$.
