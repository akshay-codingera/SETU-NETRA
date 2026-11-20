# SETU-NETRA: KORA KAAGAZ FEATURE GAP ANALYSIS & PRESERVATION MATRIX
**System Version:** 2.0.0-RC1 (Kora Kaagaz Specification)  
**Document Classification:** Component Gap Analysis, Preservation Matrix & Refactoring Strategy (Revised for V2.0.0-RC1 Corrections)  
**Reference Codebase:** SETU-NETRA V1.1.0 (185 Passing Tests, 5 Passing Validation Audits)  
**Date:** March 2026  

---

## 1. Executive Summary & Assessment Methodology

An exhaustive code-level audit was conducted across all 11 existing subsystems in `d:/Projects/Setu-Netra` to evaluate readiness for the **Kora Kaagaz** product specification.

The audit confirms that SETU-NETRA V1.1.0 possesses a deeply robust, mathematically sound, and rigorously tested algorithmic engine. The core challenge is not algorithmic—it is **architectural elevation**:
* The algorithmic core (retrieval, layout extraction, routing, scheduling, local inference, and citation verification) is $100\%$ implemented and empirically validated.
* The primary evolution occurs in the **transport layer** (deploying FastAPI + Uvicorn as an additive ASGI layer while preserving legacy `app.py` as a fallback), the **security/isolation layer** (adding RBAC and shared SQLite tables scoped by `workspace_id`), and the **presentation/interaction layer** (elevating the UI to the Kora Kaagaz parchment aesthetic and building the Live Intelligence Map and The Well visualizers).

---

## 2. Granular Feature Gap Matrix Across the 12 Modules

| Module ID & Name | Existing Code Status | Underlying Existing Files | Feature Gap & Required Implementation |
| :--- | :---: | :--- | :--- |
| **[A] Public Manifesto & Playground** | `Missing` | None (Direct UI) | Build public landing page, interactive architectural manifesto, and guest sandbox with strict rate-limiting (5 QPM, 256 token ceiling) and pre-loaded benchmark docs. |
| **[B] Authenticated Workspace Desk** | `Partially Implemented` | `core/database.py`, `ui/app.py` | Database stores documents, but lacks `workspaces`, `users`, and `sessions` tables. Add shared SQLite table scoping via `workspace_id`, workspace switcher, file drag-and-drop, and SHA-256 deduplication HUD. |
| **[C] Pristine Document QA Canvas** | `Backend Only` | `ocr/processor.py`, `retrieval/passage_retriever.py`, `models/pipeline.py` | Ingestion, OCR bounding boxes, and retrieval work. Build multi-page high-resolution canvas with sub-pixel bounding box overlays $[0.0, 1.0]$ and interactive citation pills. (Handwritten OCR is unverified). |
| **[D] Knowledge Graph Explorer** | `Partially Implemented` | `models/graph_builder.py` | Entity and relation extraction classes exist in backend. Build 2D force-directed interactive graph visualization canvas. |
| **[E] Spatial Provenance Deck** | `Backend Only` | `retrieval/citation_verifier.py`, `models/ollama_adapter.py` | Tripartite verification and `<think>` extraction work. Build split-screen UI showing raw thinking traces, lexical overlap scores, and crop bounding box views. |
| **[F] Report Studio** | `Missing` | None | Build markdown/LaTeX research report editor with one-click drag-and-drop citation snippet insertion and PDF export. |
| **[G] Model Management & Registry** | `Fully Implemented (Backend)` | `models/registry.py`, `models/ollama_adapter.py`, `models/smollm_adapter.py` | Registry and adapters work. Build UI dashboard for Ollama daemon warm-up, context size controls, and cloud standby toggles (in Hosted Public Mode). |
| **[H] Live Intelligence Map** | `Missing (UI)` | `models/pipeline.py`, `core/telemetry.py` | Pipeline stages record timestamps, but no real-time event bus exists. Implement in-memory `EventBus` with correlation IDs, SSE streaming, and SVG/Canvas topological flow graph. |
| **[I] The Well (Capacity Reservoir)** | `Missing (UI)` | `core/hardware.py` | Native Windows `kernel32` hardware telemetry works. Implement fluid dynamics canvas simulation driven by genuine memory headroom, QPS, and worker vortex currents. |
| **[J] Owner Control Canvas** | `Backend Only` | `models/router.py`, `models/worker_pool.py`, `models/schedulers.py` | All 6 schedulers and dynamic weights exist in backend. Build master administrative UI with live weight sliders and emergency killswitch. |
| **[K] Faculty Observer Deck** | `Backend Only` | `tests/`, `benchmarks/`, `models/metrics.py` | Empirical benchmarks exist in SQLite and JSON. Build live KaTeX derivation viewer, Wilson score confidence charts for binary proportions (with explicit sample size $n$), and NDJSON export desk. |
| **[L] Security & Audit Log** | `Partially Implemented` | `core/database.py`, `core/logger.py` | Query logs persist to SQLite. Add Argon2id auth, RBAC middleware, tamper-evident SHA-256 chained audit ledger, and dual application/OS firewall egress enforcement. |

---

## 3. Component Preservation Matrix (Strict Read-Only Directives)

To prevent regressions, the following modules in `src/setu_netra/` are certified as **VERIFIED CORE** and must **NEVER** be rewritten, refactored from scratch, or modified in any backward-incompatible way:

```
src/setu_netra/
  +-- core/
  |     +-- database.py          [PRESERVE & EXTEND] - Base schema is validated; extend with new tables via migration functions.
  |     +-- hardware.py          [PRESERVE AS-IS]   - Native Windows kernel32 memory counters are 100% verified.
  |     +-- logger.py            [PRESERVE AS-IS]   - Structured JSON logging verified across 185 tests.
  +-- ocr/
  |     +-- processor.py         [PRESERVE AS-IS]   - EasyOCR and layout extraction are fully functional.
  +-- retrieval/
  |     +-- passage_retriever.py [PRESERVE AS-IS]   - Hybrid dense/lexical retrieval is validated.
  |     +-- citation_verifier.py [PRESERVE AS-IS]   - Tripartite verification taxonomy is mathematically sound.
  +-- models/
        +-- registry.py          [PRESERVE AS-IS]   - Unified model registry and metadata contracts.
        +-- router.py            [PRESERVE AS-IS]   - Dual-tier adaptive scoring formula.
        +-- worker_pool.py       [PRESERVE AS-IS]   - Worker capacity and health state machine.
        +-- schedulers.py        [PRESERVE AS-IS]   - All 6 validated scheduling algorithms.
        +-- ollama_adapter.py    [PRESERVE AS-IS]   - Qwen 3.5 2B integration, thinking trace parser, and 1-concurrency semaphore.
        +-- smollm_adapter.py    [PRESERVE AS-IS]   - Transformers CPU SLM integration.
        +-- pipeline.py          [PRESERVE AS-IS]   - End-to-end inference coordination.
```

### Architectural Preservation Strategy:
Instead of altering core files, new Kora Kaagaz capabilities are added by **wrapping and composing** existing modules:
1. **Additive API Architecture:** `src/setu_netra/api/` invokes `InferencePipeline` directly inside non-blocking asynchronous thread pools (`anyio.to_thread.run_sync`). The legacy `app.py` remains untouched as an operational fallback.
2. **Minimal Backward-Compatible Hooks:** Pipeline instrumentation inspects existing telemetry hooks first. Any minimal instrumentation hooks added must be backward-compatible and mathematically proven not to alter routing, retrieval, scheduling, or inference outputs.
3. **Model Concurrency Preservation:** The 1-request concurrency semaphore for local Ollama is preserved across all thread pool dispatches.

---

## 4. Technical Debt Elimination Plan

### 4.1 Debt Item 1: Monolithic Synchronous Server vs. Additive ASGI Layer
* **Current Issue:** A single 1,440-line file (`app.py`) combining raw `http.server.ThreadingHTTPServer`, handcrafted regexes, static HTML strings, and synchronous pipeline calls.
* **Risk:** Long-running local SLM generative requests (5–20s) tie up OS threads, limiting concurrent capacity and preventing SSE streaming.
* **Remediation Plan:**
  1. Build an additive FastAPI application package in `src/setu_netra/api/`:
     * `src/setu_netra/api/main.py`: ASGI entrypoint with lifespan events and RFC 9457 error handlers.
     * `src/setu_netra/api/event_bus.py`: Single-process in-memory pub/sub with 2048-event ring buffer, correlation IDs, 15s keep-alive pings, and slow-client frame dropping.
     * `src/setu_netra/api/routers/`: Modular route handlers for auth, workspaces, documents, query, telemetry, admin, and observer.
  2. Keep `src/setu_netra/ui/app.py` active and intact as an operational fallback until all Phase 6 acceptance criteria pass.

### 4.2 Debt Item 2: Flat Single-Tenant Database Namespace
* **Current Issue:** SQLite schema stores all documents and passages in a global namespace with no workspace or user isolation.
* **Risk:** Cross-project data contamination and inability to isolate research teams.
* **Remediation Plan:**
  1. Execute a non-destructive, versioned, and reversible schema migration:
     * Add `workspaces`, `users`, `sessions`, and `audit_ledger` tables.
     * Add `workspace_id TEXT DEFAULT 'default'` to existing tables.
     * Migrate all existing V1.1.0 data cleanly into the `'default'` workspace.
  2. Enforce object-level workspace authorization on every database query and API operation.
  3. Document the SQLite WAL single-writer constraint (`busy_timeout = 5000`) and establish clear threshold criteria for when a PostgreSQL migration is warranted.

### 4.3 Debt Item 3: Polling Telemetry vs. Real-Time Streaming
* **Current Issue:** Legacy UI polls `/api/telemetry` every 2000ms.
* **Risk:** HTTP overhead and laggy visual updates for The Well and Live Intelligence Map.
* **Remediation Plan:**
  * Implement native SSE (`text/event-stream`) over HTTP/1.1 with `Last-Event-ID` reconnection replay.
  * Emit periodic hardware ticks every 1000ms and immediate event packets with unique correlation IDs upon every pipeline stage transition.
  * Formulate explicit mathematical transformations for The Well (RAM headroom, request arrival rate, worker token velocity, processing capacity) using exponential smoothing and zero fake activity.
