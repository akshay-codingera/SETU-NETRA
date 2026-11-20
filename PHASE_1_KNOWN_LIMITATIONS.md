# SETU-NETRA V2.0.0-RC1 — PHASE 1 KNOWN LIMITATIONS & ARCHITECTURAL BOUNDARIES
**Milestone:** Phase 1 — Foundation, Additive ASGI Engine & Core Event Bus  
**Document Classification:** Engineering Limitations & Operational Boundaries  
**Date:** March 2026  

---

## 1. Purpose of this Document

In accordance with the scientific ethos of **Kora Kaagaz** (The Pristine Parchment of Truth), this document explicitly records all known constraints, boundaries, and performance ceilings of the Phase 1 implementation. These items are tracked for progressive resolution across subsequent milestones (Phases 2 through 6).

---

## 2. Documented Technical Limitations

### 2.1 Single-Process In-Memory EventBus
* **Limitation:** The current `EventBus` (`src/setu_netra/api/event_bus.py`) operates strictly within a single Python process memory space.
* **Impact:** In the current Local Research Mode, Uvicorn runs as a single worker process on port 8502, which is optimal for consumer hardware (12-vCPU i5, 16 GB RAM). However, if Uvicorn were launched with multiple worker processes (`--workers 4`), each worker process would possess an isolated EventBus instance, preventing SSE cross-worker event broadcasting.
* **Resolution Path:** For multi-worker deployments in Hosted Public Mode, an external pub/sub broker (e.g., Redis or Dragonfly) will be introduced via dependency inversion without modifying the `EventBus` interface.

### 2.2 Ollama CPU Generation Latency vs. Scheduler Timeout
* **Limitation:** When Qwen 3.5 2B executes on CPU with deep internal reasoning enabled (`think=True`), it can generate between 500 and 800 thinking tokens. At standard CPU generation speeds of $13.5\text{ tok/s}$, generation time reaches $40\text{ to }55\text{ seconds}$. The `AdaptiveResilientScheduler` enforces an overall request timeout of $30.0\text{ seconds}$, which triggers a `TIMEOUT` status if reasoning is unrestricted.
* **Workaround & Mitigation:**
  1. Passing `think="strip"` or `think=False` bypasses the verbose reasoning trace, allowing Qwen to directly synthesize the answer in **$0.58\text{ to }12.0\text{ seconds}$**, well within the 30.0s scheduler window.
  2. For deep reasoning queries in Phase 5, the scheduler timeout parameter will be exposed dynamically through the Owner Control Canvas.

### 2.3 SQLite WAL Single-Writer Serialization
* **Limitation:** SQLite in WAL mode permits unlimited concurrent readers, but serializes all write transactions.
* **Current Safeguard:** Configured `busy_timeout = 5000ms`. Under the current Phase 1 operational profile (single-user / small-team testing), write lock contention is negligible ($<0.01\%$).
* **Threshold Boundary:** If concurrent write throughput exceeds 50 writes/second or `SQLITE_BUSY` errors occur on $>5\%$ of requests, migration to PostgreSQL will be triggered according to the criteria defined in `SETU_NETRA_EXISTING_ARCHITECTURE.md`.

### 2.4 Intentional Scope Boundaries (Deferred to Future Phases)
To maintain strict discipline and prevent premature complexity:
1. **Authentication & Multi-Tenancy (Phase 2):** Phase 1 endpoints operate without user credentials. Multi-tenant workspace scoping (`workspace_id`), Argon2id authentication, and reversible SQLite migrations are scheduled for Phase 2.
2. **Kora Kaagaz Editorial UI & Canvas (Phase 3):** Phase 1 provides the backend API and SSE telemetry highway. The interactive parchment paper canvas with sub-pixel bounding box overlays will be delivered in Phase 3.
3. **The Well & Live Map Visualizers (Phase 4):** Real-time SVG topological graph rendering and fluid dynamics WebGL canvas for The Well will be implemented in Phase 4.
4. **Faculty Observer Deck (Phase 5):** Live KaTeX formula derivation viewer and Wilson score confidence charts will be delivered in Phase 5.
5. **Handwritten OCR:** Explicitly declared **UNVERIFIED and OUT OF SCOPE**. Certified strictly for printed, scanned, and digital academic, legal, and financial documents.

---

## 3. Operational Guidelines for Evaluators

1. **Port Separation:**
   * Legacy UI & REST Hub: `http://127.0.0.1:8501/`
   * New Additive ASGI API & Telemetry: `http://127.0.0.1:8502/`
2. **Local Security:** Both servers are strictly bound to loopback `127.0.0.1`.
3. **Verification Command:** To re-verify all 196 tests at any time:
   ```powershell
   $env:PYTHONPATH="src"; .venv\Scripts\python -m unittest discover -s tests -p "test_*.py"
   ```
