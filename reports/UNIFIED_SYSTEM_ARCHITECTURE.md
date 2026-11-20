# SETU-NETRA: Unified System Architecture Specification
## Integrated Document Intelligence, Adaptive Model Routing, & AI Traffic Management

**Report ID:** SETU-UNIFIED-ARCH-006  
**Date:** November 9, 2026  
**Audience:** Technical Committee, System Architects, Developers  
**Scope:** Complete Architectural Synthesis of Both Research Directions  

---

## 1. Grand Unified Architecture

SETU-NETRA seamlessly unifies two distinct engineering disciplines: **Evidence-Grounded Document Understanding** and **Capacity-Aware AI Inference Orchestration**.

```mermaid
flowchart TD
    subgraph UI_Layer["Layer 1: Unified User Workspaces"]
        WS1["Workspace 1: Document Intelligence\n- PDF / Image Upload & Preview\n- Bounding Box Highlighting\n- Evidence-Grounded Answers\n- Conversational Multi-Turn QA"]
        WS2["Workspace 2: AI Orchestration Dashboard\n- Real-Time Model Registry\n- Live Worker Queues & Telemetry\n- Active Routing Policy (RR, LOR, SECT, CAS)\n- Latency (p50/p95/p99) & Throughput Charts"]
    end

    subgraph Document_Engine["Layer 2: Document Intelligence Engine"]
        Ingest["Multi-Format Ingestion\n(.pdf, .png, .jpg, .tiff, .docx, .txt)"]
        OCR_Sub["EasyOCR Engine\n(CRAFT Detection + CRNN Recognition)"]
        Struct_Sub["Structural Layout Reconstructor\n- Recursive XY-Cut Multi-Column\n- Line & Block Clustering\n- MCQ Option-to-Question Association"]
        Store_Sub[("Persistent SQLite Store (WAL)\n- Documents, Pages, Blocks\n- SHA-256 Deduplication\n- Raw float32 Embeddings")]
        Ret_Sub["Hybrid Document Retriever\n- Rectified Dense Cosine\n- Lexical Overlap\n- Near-Duplicate & Header Suppression"]
        Synth_Sub["Evidence Context Synthesizer\n- Token Budget Enforcement\n- Citation Markers [Doc, Page, Block]"]
    end

    subgraph Routing_Engine["Layer 3: Adaptive Model Routing & Cascading"]
        Router["Task & Complexity Classifier\n- Detects Task (OCR, Embed, QA, Reasoning)\n- Computes Prompt Tokens & Budget"]
        Registry["Model Registry Catalog\n- Model Profiles & Hardware Specs\n- Quality Benchmark Scores\n- P50/P95 Historical Latency\n- Memory Footprint (MB)"]
        Cascade["Evidence-Grounded Cascade Controller\n- Tier 1: Lightweight Local SLM\n- Verification Check (Citation & Factuality)\n- Escalation to Tier 2 Heavy Model"]
    end

    subgraph Traffic_Engine["Layer 4: Intelligent AI Traffic Management"]
        Scheduler["Pluggable Scheduler Policies\n- Round Robin (RR)\n- Least Outstanding Requests (LOR)\n- Shortest Estimated Completion Time (SECT)\n- Capacity-Aware Scheduling (CAS)\n- Adaptive Resilient Scheduling (ARS)"]
        Telemetry["Telemetry Monitor\n- CPU Load & Free Physical RAM\n- Inflight Requests & Queue Lengths\n- Exponential Moving Average Latency"]
        Workers["Worker Pool Replicas\n- Worker 1 (Local CPU Thread/Process)\n- Worker 2 (Local CPU Thread/Process)\n- Worker K (Remote / Subprocess Adapter)"]
    end

    subgraph Verification_Engine["Layer 5: Evidence Grounding & Verification"]
        Verifier["Tripartite Factuality & Citation Auditor\n1. Evidence-Backed Answer (Strict Citation)\n2. General Model Knowledge (Warning Tag)\n3. Unsupported / Abstained Response"]
    end

    %% Workflows
    WS1 --> Ingest
    Ingest --> OCR_Sub --> Struct_Sub --> Store_Sub
    WS1 --> Router
    Router --> Registry
    Router --> Cascade
    Cascade --> Ret_Sub
    Store_Sub --> Ret_Sub
    Ret_Sub --> Synth_Sub
    Synth_Sub --> Scheduler
    Scheduler --> Telemetry
    Telemetry --> Workers
    Workers --> Verifier
    Verifier --> WS1
    
    Telemetry -.-> WS2
    Registry -.-> WS2
    Scheduler -.-> WS2
```

---

## 2. End-to-End Execution Lifecycle Trace

Below is the chronological trace of a document being ingested and a user question being processed:

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant UI as Workspace 1 (UI)
    participant Ingest as Document Ingestion
    participant OCR as OCR Subsystem
    participant Struct as Structure Reconstructor
    participant Store as SQLite Store
    participant Router as Model Router
    participant Scheduler as Traffic Scheduler
    participant Worker as Worker Replica
    participant Verifier as Factuality Verifier

    %% Ingestion Phase
    User->>UI: Upload Exam Paper (e.g. sample.pdf)
    UI->>Ingest: Stream PDF bytes
    Ingest->>Ingest: Compute SHA-256 hash & decompose pages (150 DPI)
    Ingest->>OCR: Rendered page buffers
    OCR->>OCR: CRAFT region detection + CRNN text recognition
    OCR->>Struct: Raw OCR boxes
    Struct->>Struct: Recursive XY-Cut -> Line Grouping -> MCQ Association
    Struct->>Store: Persist document, pages, blocks, and embeddings
    Store-->>UI: Ingestion Complete (Document Indexed)

    %% Query & Routing Phase
    User->>UI: Query: "What is primary memory?"
    UI->>Router: Submit Query + Session Document ID
    Router->>Store: Retrieve Top-K passages via DocumentRetriever
    Store-->>Router: Top-K Passages with Bounding Boxes
    Router->>Router: Format token-budgeted prompt with citation instructions
    Router->>Router: Select Model (e.g. Tier 1: Qwen2.5-0.5B-Q4)
    
    %% Traffic Scheduling Phase
    Router->>Scheduler: Dispatch Request (Task: QA, Target: Qwen2.5)
    Scheduler->>Scheduler: Inspect Worker Telemetry (LOR / SECT / CAS)
    Scheduler->>Worker: Enqueue to Worker 1
    Worker->>Worker: Execute Local Inference on CPU
    Worker-->>Scheduler: Candidate Generation + Generated Citations
    
    %% Verification Phase
    Scheduler->>Verifier: Audit Answer
    Note over Verifier: Cross-check asserted facts against retrieved passages.<br>Are citations valid and supported?
    Verifier-->>UI: Verified Evidence-Backed Answer with Clickable Bounding Boxes
    UI->>User: Display Answer + Highlight Bounding Box on Original PDF
```

---

## 3. Inter-Subsystem Communication Contracts

All communication between subsystems is strictly typed using Python dataclasses and Pydantic schemas:

### Contract 1: `InferenceRequest` (Router $\to$ Traffic Scheduler)
```python
@dataclass
class InferenceRequest:
    request_id: str                   # Unique UUID v4
    task_type: str                    # 'qa' | 'embedding' | 'ocr' | 'classification'
    target_model_id: str              # Selected by Model Router (e.g. 'all-minilm-l6-v2')
    prompt_or_payload: Any            # Synthesized context prompt or image buffer
    priority: int                     # 1 (Critical interactive) to 5 (Background batch)
    timeout_ms: float                 # Request deadline (e.g. 15000.0 ms)
    max_tokens: int                   # Generation budget
    created_at_iso: str               # Arrival timestamp for queue wait calculation
```

### Contract 2: `WorkerTelemetry` (Worker Pool $\to$ Scheduler)
```python
@dataclass
class WorkerTelemetry:
    worker_id: str                    # 'worker_01'
    status: str                       # 'IDLE', 'BUSY', 'DEGRADED', 'UNHEALTHY'
    active_requests: int              # Currently computing requests
    queue_depth: int                  # Requests waiting in worker's buffer
    cpu_percent: float                # Process CPU utilization
    ram_resident_mb: float            # Process memory footprint (RSS MB)
    ema_latency_ms: float             # Exponential moving average service time
    total_failures: int               # Cumulative exception count
```

### Contract 3: `VerifiedAnswer` (Verification Engine $\to$ UI)
```python
@dataclass
class VerifiedAnswer:
    answer_text: str                  # Generated textual answer
    epistemic_status: str             # 'EVIDENCE_BACKED' | 'GENERAL_KNOWLEDGE' | 'UNSUPPORTED'
    citations: List[Dict[str, Any]]   # [{'doc_id': ..., 'page': ..., 'block_id': ..., 'bbox': ...}]
    grounding_confidence: float       # Overlap score in [0.0, 1.0]
    total_latency_ms: float           # End-to-end elapsed duration
    queue_wait_ms: float              # Delay spent in scheduler queue
    executing_worker_id: str          # Telemetry attribution
    executing_model_id: str           # Model attribution
```

---

## 4. Fault Tolerance, Fault Isolation, & Graceful Degradation

1. **Worker Failure Isolation:** If a worker process crashes due to an unhandled exception or memory error, the Traffic Scheduler catches the event via heartbeat failure, marks the worker `UNHEALTHY`, and re-enqueues inflight requests to the next optimal worker replica.
2. **Resource Backpressure:** If system RAM exceeds $90\%$ or all workers are saturated, the scheduler rejects new batch requests with an explicit backpressure signal (`HTTP 429 / CAPACITY_EXCEEDED`) rather than causing the OS to freeze or kill processes via the OOM-killer.
3. **Retrieval Resilience:** If vector embeddings are corrupted or missing, `SQLiteDocumentStore` defensively skips the invalid BLOBs (verified in M6 Sprint 1), allowing lexical retrieval to proceed unimpeded.
4. **Offline Autonomy:** The system remains $100\%$ operational offline without internet connectivity. If cloud LLM endpoints are unreachable, the router seamlessly falls back to local quantized SLMs or rule-based synthesis.
