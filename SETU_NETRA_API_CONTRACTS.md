# SETU-NETRA: KORA KAAGAZ API CONTRACTS & PROTOCOL SPECIFICATION
**System Version:** 2.0.0-RC1 (Kora Kaagaz Specification)  
**Protocol Standards:** REST (HTTP/1.1 over TLS), Server-Sent Events (SSE), RFC 9457 Problem Details  
**Base URL:** `https://127.0.0.1:8501/api/v1` (or `http://127.0.0.1:8501/api/v1` in Local Research Mode)  
**Date:** March 2026  

---

## 1. Overview & Architectural Principles

The SETU-NETRA Kora Kaagaz API provides a high-performance, asynchronous interface for document intelligence, spatial provenance verification, model orchestration, and real-time observability.

### Core Protocol Design Rules:
1. **Strict Versioning:** All endpoints are strictly namespaced under `/api/v1`.
2. **RFC 9457 Problem Details Error Standard:** All client and server errors return standardized `application/problem+json` bodies complying with **RFC 9457** (which obsoletes RFC 7807).
3. **Correlation Tracking:** Every request accepted by the system is assigned a unique correlation ID (`X-Correlation-ID: corr_<uuid4>`). This ID is returned in the response header and embedded in every downstream telemetry and SSE event.
4. **Session & Cookie Security:** Session authentication relies on cryptographically signed, `HttpOnly`, `Secure` (in HTTPS deployments), and context-appropriate `SameSite=Lax` cookies, supplemented with an `X-CSRF-Token` header for state-mutating requests (`POST`, `PUT`, `DELETE`).
5. **Real-Time Push via Server-Sent Events (SSE):** Long-lived telemetry streams and generative token flows utilize native SSE (`text/event-stream`) over HTTP/1.1. Experimental HTTP/2 support is strictly optional and not a prerequisite.
6. **Deterministic Spatial Coordinates:** All bounding box coordinates are normalized floats within $[0.0, 1.0]$ relative to the underlying page canvas dimensions:
   $$\text{box} = [x_1, y_1, x_2, y_2] \quad \text{where} \quad 0.0 \le x_1 \le x_2 \le 1.0, \quad 0.0 \le y_1 \le y_2 \le 1.0$$
7. **Workspace Isolation:** Every resource and query is strictly scoped to an authorized `workspace_id`. Cross-workspace queries are rejected at the authorization layer.

---

## 2. Standard Error Format (RFC 9457 Problem Details)

Every non-$2\text{xx}$ HTTP response strictly returns `Content-Type: application/problem+json` following RFC 9457:

```json
{
  "type": "https://setu-netra.internal/errors/INSUFFICIENT_MEMORY",
  "title": "Insufficient Hardware Memory Headroom",
  "status": 503,
  "detail": "Requested model 'ollama/qwen3.5:2b' requires 2.50 GB free RAM, but current headroom is 1.84 GB.",
  "instance": "/api/v1/query",
  "correlation_id": "corr_88f0c1a2-3b4c-4e5f-9a1b-2c3d4e5f6a7b",
  "timestamp": "2026-03-24T14:32:10.452Z",
  "code": "ERR_SYSTEM_MEMORY_HEADROOM",
  "invalid_params": []
}
```

---

## 3. Authentication & Session Endpoints (`/api/v1/auth`)

### 3.1 `POST /api/v1/auth/login`
Authenticates a user using Argon2id, generates a new session token, and rotates any existing session identifier to prevent session fixation attacks.

* **Headers:** `Content-Type: application/json`, `X-Correlation-ID: corr_<uuid>` (optional)
* **Request Body:**
  ```json
  {
    "username": "faculty_reviewer",
    "password": "SecurePassword123!"
  }
  ```
* **Success Response (`200 OK`):**
  * **Headers:**
    * `Set-Cookie: setu_session=s%3A...; HttpOnly; Secure; SameSite=Lax; Path=/`
    * `X-CSRF-Token: csrf_94b1a82e...`
    * `X-Correlation-ID: corr_88f0c1a2...`
  ```json
  {
    "user_id": "usr_94b1a82e",
    "username": "faculty_reviewer",
    "display_name": "Dr. A. Sharma",
    "role": "FACULTY_OBSERVER",
    "active_workspace_id": "ws_research_main",
    "csrf_token": "csrf_94b1a82e...",
    "permissions": [
      "document:read",
      "query:execute",
      "observer:audit",
      "benchmark:export"
    ],
    "expires_at": "2026-03-25T14:30:00Z"
  }
  ```
* **Errors:**
  * `401 Unauthorized` (RFC 9457): Invalid credentials.
  * `429 Too Many Requests` (RFC 9457): Exceeded 5 failed attempts in 60 seconds.

### 3.2 `POST /api/v1/auth/logout`
Revokes active session token in SQLite persistence, invalidates session cookie, and logs session termination in the audit ledger.
* **Headers:** `X-CSRF-Token: csrf_...`
* **Success Response (`200 OK`):**
  * **Headers:** `Set-Cookie: setu_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`
  ```json
  {
    "status": "LOGGED_OUT",
    "message": "Session revoked and terminated successfully."
  }
  ```

### 3.3 `GET /api/v1/auth/session`
Returns profile, active role, and permissions for the currently authenticated session cookie.
* **Success Response (`200 OK`):** Same schema as login response body.
* **Guest Fallback (`200 OK` when unauthenticated):**
  ```json
  {
    "user_id": "guest_anon",
    "username": "guest",
    "display_name": "Guest Researcher",
    "role": "GUEST",
    "active_workspace_id": "ws_public_sandbox",
    "csrf_token": null,
    "permissions": [
      "document:read",
      "query:execute_restricted"
    ],
    "expires_at": null
  }
  ```

---

## 4. Workspace Management (`/api/v1/workspaces`)

Multi-tenancy operates strictly via shared SQLite tables filtered by `workspace_id`.

### 4.1 `GET /api/v1/workspaces`
Lists workspaces accessible to the authenticated user.
* **Success Response (`200 OK`):**
  ```json
  {
    "workspaces": [
      {
        "workspace_id": "ws_research_main",
        "name": "Transformer Attention Audits",
        "description": "Comparative study of spatial attention in document QA",
        "document_count": 8,
        "query_count": 142,
        "created_at": "2026-03-01T09:00:00Z",
        "updated_at": "2026-03-24T12:00:00Z"
      }
    ]
  }
  ```

### 4.2 `POST /api/v1/workspaces`
Creates a new workspace namespace.
* **Headers:** `X-CSRF-Token: csrf_...`
* **Request Body:**
  ```json
  {
    "name": "Clinical Trial Papers",
    "description": "Analysis of Phase III oncology trials"
  }
  ```
* **Success Response (`201 Created`):** Returns the created workspace object.

---

## 5. Document Ingestion & Spatial Representation (`/api/v1/documents`)

### 5.1 `POST /api/v1/documents/upload`
Uploads a document (PDF, PNG, JPG) to the specified workspace. Initiates background extraction pipeline.

* **Headers:** `Content-Type: multipart/form-data`, `X-CSRF-Token: csrf_...`
* **Form Fields:**
  * `file`: Binary file contents.
  * `workspace_id`: String (optional; defaults to active session workspace).
* **Success Response (`202 Accepted`):**
  ```json
  {
    "document_id": "doc_a4f91b2c",
    "workspace_id": "ws_research_main",
    "filename": "1706.03762v7.pdf",
    "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    "status": "PROCESSING",
    "stage": "OCR_LAYOUT_RECONSTRUCTION",
    "progress_percent": 35.0,
    "correlation_id": "corr_88f0c1a2-3b4c-4e5f-9a1b-2c3d4e5f6a7b",
    "created_at": "2026-03-24T14:35:00Z"
  }
  ```

### 5.2 `GET /api/v1/documents/{document_id}`
Returns document processing status and metadata. Strictly verifies that `document_id` belongs to the user's active workspace.
* **Success Response (`200 OK`):**
  ```json
  {
    "document_id": "doc_a4f91b2c",
    "workspace_id": "ws_research_main",
    "filename": "1706.03762v7.pdf",
    "page_count": 15,
    "block_count": 142,
    "status": "READY",
    "ocr_confidence_mean": 0.942,
    "created_at": "2026-03-24T14:35:00Z",
    "completed_at": "2026-03-24T14:35:12Z"
  }
  ```

### 5.3 `GET /api/v1/documents/{document_id}/pages/{page_number}/image`
Returns rendered high-resolution PNG bitmap of the requested page canvas.
* **Query Parameters:** `dpi=150`
* **Success Response (`200 OK`):**
  * **Headers:** `Content-Type: image/png`, `Cache-Control: private, max-age=86400`
  * **Body:** Raw PNG byte stream.

### 5.4 `GET /api/v1/documents/{document_id}/blocks`
Retrieves all spatially indexed bounding blocks for the document.
* **Query Parameters:** `page_number=1` (optional filter).
* **Success Response (`200 OK`):**
  ```json
  {
    "document_id": "doc_a4f91b2c",
    "page_number": 1,
    "blocks": [
      {
        "block_id": "blk_p1_003",
        "page_number": 1,
        "reading_order": 3,
        "block_type": "paragraph",
        "bounding_box": [0.12, 0.34, 0.88, 0.42],
        "text": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
        "ocr_confidence": 0.965
      }
    ]
  }
  ```

---

## 6. Query Execution & Inference Pipeline (`/api/v1/query`)

### 6.1 `POST /api/v1/query` (Unified Inference Endpoint)
Submits a user query against one or more documents within the active workspace. Supports synchronous JSON responses and real-time SSE streaming. Dispatches CPU inference into bounded worker threads without blocking the ASGI event loop.

* **Headers:**
  * `Content-Type: application/json`
  * `Accept: application/json` OR `Accept: text/event-stream`
  * `X-Correlation-ID: corr_<uuid>` (optional; generated if absent)
* **Request Body:**
  ```json
  {
    "query": "What is the computational complexity per layer for Self-Attention vs Recurrent layers?",
    "document_ids": ["doc_a4f91b2c"],
    "target_model": "auto",
    "stream": true,
    "think_mode": "strip",
    "max_tokens": 512,
    "top_k_passages": 5
  }
  ```

#### Synchronous Response (`Accept: application/json`, `stream: false`):
* **Status (`200 OK`):**
  * **Headers:** `X-Correlation-ID: corr_88f0c1a2...`
  ```json
  {
    "query_id": "qry_88f0c1a2",
    "correlation_id": "corr_88f0c1a2-3b4c-4e5f-9a1b-2c3d4e5f6a7b",
    "query": "What is the computational complexity per layer for Self-Attention vs Recurrent layers?",
    "answer": "As shown in Table 1, Self-Attention has a computational complexity per layer of O(1) sequential operations and O(n² · d) total complexity...",
    "thinking_trace": null,
    "verification_classification": "EVIDENCE_BACKED",
    "confidence_score": 0.934,
    "selected_model": "ollama/qwen3.5:2b",
    "selected_worker": "ollama/qwen3.5:2b_w1",
    "scheduler_used": "adaptive",
    "latency_breakdown_ms": {
      "query_analysis": 1.2,
      "routing_decision": 0.8,
      "dense_retrieval": 14.5,
      "lexical_retrieval": 3.2,
      "model_inference": 1420.0,
      "citation_verification": 12.1,
      "total": 1451.8
    },
    "citations": [
      {
        "citation_id": "cit_001",
        "document_id": "doc_a4f91b2c",
        "page_number": 6,
        "block_id": "blk_p6_014",
        "bounding_box": [0.15, 0.45, 0.85, 0.58],
        "exact_quote": "Self-Attention: O(n² · d) per layer, O(1) sequential operations.",
        "lexical_overlap_score": 0.88,
        "semantic_cosine_score": 0.94
      }
    ]
  }
  ```

#### Streaming SSE Response (`Accept: text/event-stream`, `stream: true`):
Emits structured SSE events with correlation IDs:

```
event: ROUTING_DECIDED
id: 1001
data: {"correlation_id":"corr_88f0c1a2...","query_id":"qry_88f0c1a2","model_id":"ollama/qwen3.5:2b","worker_id":"ollama/qwen3.5:2b_w1","scheduler":"adaptive"}

event: PASSAGES_RETRIEVED
id: 1002
data: {"correlation_id":"corr_88f0c1a2...","query_id":"qry_88f0c1a2","count":5,"top_scores":[0.892, 0.841, 0.765]}

event: TOKEN_DELTA
id: 1003
data: {"correlation_id":"corr_88f0c1a2...","delta":"As"}

event: TOKEN_DELTA
id: 1004
data: {"correlation_id":"corr_88f0c1a2...","delta":" shown in Table 1,"}

event: CITATION_VERIFIED
id: 1005
data: {"correlation_id":"corr_88f0c1a2...","citation_id":"cit_001","page_number":6,"bounding_box":[0.15,0.45,0.85,0.58],"classification":"EVIDENCE_BACKED"}

event: QUERY_COMPLETED
id: 1006
data: {"correlation_id":"corr_88f0c1a2...","status":"SUCCESS","total_latency_ms":1451.8,"tokens_generated":48}
```

---

## 7. Real-Time Telemetry & SSE Streaming (`/api/v1/events/stream`)

### 7.1 `GET /api/v1/events/stream`
Central Server-Sent Events highway powering the **Live Intelligence Map** and **The Well**.

* **Headers:** `Accept: text/event-stream`
* **Query Parameters:** `workspace_id=ws_research_main` (optional filter).
* **Client Request Header on Reconnect:** `Last-Event-ID: 1042`
* **Single-Process Scope:** The EventBus operates as an in-process async pub/sub engine. In a multi-worker deployment, an external broker (Redis/Dragonfly) would be required.
* **Keep-Alive Heartbeats:** Emits `: ping\n\n` comments every 15 seconds to prevent client timeout.
* **Slow Client Handling:** Subscriptions have a bounded queue of 256 frames. If a client falls behind, oldest frames are dropped, and a `CLIENT_BACKPRESSURE_WARNING` event is delivered.

#### Periodic Event Examples:
1. `HARDWARE_TICK` (every 1000ms):
   ```json
   {
     "event_id": 1045,
     "timestamp": "2026-03-24T14:36:00.100Z",
     "cpu_percent": 24.5,
     "ram_total_mb": 16075,
     "ram_used_mb": 10420,
     "ram_headroom_mb": 5655,
     "ram_utilization_ratio": 0.648,
     "active_threads": 42
   }
   ```
2. `WELL_STATE` (every 1000ms):
   ```json
   {
     "event_id": 1046,
     "timestamp": "2026-03-24T14:36:00.100Z",
     "reservoir_depth": 0.648,
     "inflow_rate_qps": 2.4,
     "active_vortices": [
       {"worker_id": "ollama/qwen3.5:2b_w1", "angular_velocity_rad_s": 8.5, "status": "BUSY"},
       {"worker_id": "smollm2_worker_0", "angular_velocity_rad_s": 0.0, "status": "IDLE"}
     ],
     "sediment_accumulation_ratio": 0.142,
     "thermal_coefficient": 0.38
   }
   ```

---

## 8. Owner Control Canvas & Administration (`/api/v1/admin`)

*Strictly requires `role: OWNER` and valid `X-CSRF-Token`.*

### 8.1 `GET /api/v1/admin/routing-policy`
Retrieves live adaptive router configuration weights.
* **Success Response (`200 OK`):**
  ```json
  {
    "cost_weight": 0.25,
    "latency_weight": 0.35,
    "quality_weight": 0.25,
    "memory_weight": 0.15,
    "active_scheduler": "adaptive",
    "cloud_egress_locked": false,
    "ollama_concurrency_ceiling": 1
  }
  ```

### 8.2 `PUT /api/v1/admin/routing-policy`
Hot-tunes routing weights dynamically with zero server restart.
* **Request Body:**
  ```json
  {
    "cost_weight": 0.10,
    "latency_weight": 0.20,
    "quality_weight": 0.50,
    "memory_weight": 0.20
  }
  ```
* **Success Response (`200 OK`):** Returns updated policy.

### 8.3 `POST /api/v1/admin/circuit-breakers`
Manages circuit breaker overrides (e.g. cloud egress lockdown in Local Research Mode).
* **Request Body:**
  ```json
  {
    "breaker_name": "CLOUD_EGRESS_AIRGAP",
    "state": "TRIPPED_CLOSED"
  }
  ```
* **Success Response (`200 OK`):**
  ```json
  {
    "breaker_name": "CLOUD_EGRESS_AIRGAP",
    "status": "AIRGAP_ENFORCED",
    "message": "All cloud adapters deactivated. Zero external network egress."
  }
  ```

### 8.4 `POST /api/v1/admin/killswitch`
Emergency command: immediately drops in-flight queues and halts active local generation.
* **Request Body:** `{"reason": "Manual operator emergency drain", "confirm": true}`
* **Success Response (`200 OK`):** `{"status": "KILLED", "drained_requests": 2}`

---

## 9. Faculty Observer & Ground-Truth Verification (`/api/v1/observer`)

*Requires `role: FACULTY_OBSERVER` or `role: OWNER`.*

### 9.1 `GET /api/v1/observer/metrics`
Returns mathematically derived evaluation statistics calculated over sliding evaluation windows. Separates real user activity from synthetic benchmarks. Records sample sizes $n$ and denominators.
* **Query Parameters:** `window_size=100`, `data_source=real_user` (or `synthetic_benchmark`)
* **Success Response (`200 OK`):**
  ```json
  {
    "data_source": "real_user",
    "sample_size_n": 100,
    "retrieval": {
      "mrr_at_5": 0.842,
      "ndcg_at_5": 0.887,
      "recall_at_3": 0.720,
      "mean_cosine_similarity": 0.814
    },
    "citation_fidelity": {
      "evidence_backed_ratio": 0.860,
      "unverified_inference_ratio": 0.080,
      "general_knowledge_ratio": 0.060,
      "wilson_ci_95": {
        "evidence_backed": [0.778, 0.915],
        "sample_size_n": 100,
        "denominator": 100
      }
    },
    "latency_stats": {
      "p50_ms": 340.2,
      "p90_ms": 1420.5,
      "p99_ms": 2850.1,
      "confidence_interval_95": [310.4, 370.0]
    }
  }
  ```

### 9.2 `GET /api/v1/observer/derivations`
Returns raw mathematical formulas and current live parameter derivations for active algorithms in LaTeX formatting.
* **Success Response (`200 OK`):**
  ```json
  {
    "active_routing_formula": "\\text{Score}(m) = w_q Q(m) - w_c C(m) - w_l L(m) - w_m M(m)",
    "current_parameters": {
      "w_q": 0.25,
      "w_c": 0.25,
      "w_l": 0.35,
      "w_m": 0.15
    },
    "wilson_score_interval_formula": "\\frac{\\hat{p} + \\frac{z^2}{2n} \\pm z\\sqrt{\\frac{\\hat{p}(1-\\hat{p})}{n} + \\frac{z^2}{4n^2}}}{1 + \\frac{z^2}{n}}"
  }
  ```

### 9.3 `GET /api/v1/observer/export`
Exports raw, unredacted benchmark logs and execution traces for external peer review.
* **Query Parameters:** `format=ndjson` OR `format=sqlite`
* **Headers:** `Content-Disposition: attachment; filename="setu_netra_audit_trace.ndjson"`
* **Success Response (`200 OK`):** Streamed NDJSON trace objects.
