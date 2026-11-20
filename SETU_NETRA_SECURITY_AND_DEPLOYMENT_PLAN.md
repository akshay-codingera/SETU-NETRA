# SETU-NETRA: KORA KAAGAZ SECURITY & DEPLOYMENT ARCHITECTURE
**System Version:** 2.0.0-RC1 (Kora Kaagaz Specification)  
**Document Classification:** Security Specifications, RBAC Matrix, Airgap Protocols & Deployment Architecture (Revised for V2.0.0-RC1 Corrections)  
**Author:** AI Security & Infrastructure Reliability  
**Date:** March 2026  

---

## 1. Security Architecture Principles

SETU-NETRA is engineered for sensitive document intelligence, institutional research, and faculty auditing. Its security posture adheres to four foundational principles:

1. **Dual Deployment Modes with Strict Boundaries:** A hard architectural distinction is enforced between **Local Research Mode** (fully airgapped, verified on-device execution) and **Hosted Public Mode** (public HTTPS frontend with authenticated workspaces and authorized cloud AI endpoints). Hosted public mode is explicitly **not** described as airgapped.
2. **Cryptographic Identity & Defense-in-Depth:** Modern cryptographic standards (Argon2id password hashing, session rotation, CSRF protection, CSP headers) protect authentication and session lifecycles.
3. **Workspace Boundary Isolation:** Multi-tenancy is enforced through shared SQLite tables utilizing `workspace_id` and `tenant_id` columns with object-level authorization on every query.
4. **Tamper-Evident Governance:** Cryptographic audit logging with SHA-256 state chaining provides **tamper-evident** (verifiable, but not automatically immutable) proof of system operations.

---

## 2. Multi-Tenant Workspace Sandboxing & Data Isolation

Multi-tenancy operates strictly within a single, shared SQLite database file using `workspace_id` column partitioning, avoiding the fragility of dynamically mounting or detaching multiple SQLite database files.

```
+--------------------------------------------------------------------------------------------------+
|                                    PHYSICAL HOST STORAGE LAYOUT                                  |
+--------------------------------------------------------------------------------------------------+
|  output/setu_netra.db (Shared SQLite database in WAL mode, busy_timeout = 5000ms)               |
|    - Table: workspaces (workspace_id, name, created_at)                                          |
|    - Table: users (user_id, username, password_hash, role, created_at)                          |
|    - Table: sessions (session_id_hash, user_id, active_workspace_id, expires_at)                 |
|    - Table: documents (doc_id, workspace_id, filename, file_hash, ...)                           |
|    - Table: document_blocks (doc_id, workspace_id, block_id, bounding_box, text, ...)            |
|    - Table: audit_ledger (entry_id, prev_hash, entry_hash, action, workspace_id, ...)            |
+--------------------------------------------------------------------------------------------------+
|  data/workspaces/                                                                                |
|    +-- ws_001_physics_lab/                                                                      |
|    |     +-- documents/doc_a1b2/source.pdf, pages/, blocks.json                                  |
|    +-- ws_002_medical_audit/                                                                    |
|          +-- documents/doc_c3d4/source.pdf, pages/, blocks.json                                  |
+--------------------------------------------------------------------------------------------------+
```

### 2.1 Database Layer Isolation & Query Scoping
Every document, chunk, entity, conversation, and query is bound to an authorized `workspace_id`. All data retrieval queries enforce workspace filtering:
```sql
SELECT b.block_id, b.text, b.bounding_box 
FROM document_blocks b
JOIN documents d ON b.doc_id = d.doc_id
WHERE d.workspace_id = :active_workspace_id 
  AND d.doc_id = :target_doc_id;
```
Object-level authorization middleware inspects every API request to guarantee that the authenticated user possesses read or write permissions for the requested `workspace_id`.

### 2.2 Reversible, Versioned Schema Migrations
Database evolutions are managed by a custom, reversible migration runner (`src/setu_netra/store/migrations.py`):
1. **Non-Destructive Evolution:** New columns (`workspace_id`) are added to existing V1.1.0 tables using `ALTER TABLE ... ADD COLUMN ... DEFAULT 'default'`.
2. **Data Preservation:** All pre-existing documents, blocks, and conversations from V1.1.0 are automatically preserved under the `'default'` workspace.
3. **Reversibility:** Every migration defines both `up()` and `down()` transformations with automated rollback capabilities.

### 2.3 SQLite WAL Single-Writer Constraint & PostgreSQL Thresholds
* **The Constraint:** Under Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), SQLite supports unlimited concurrent readers, but enforces a strict single-writer lock. Concurrent write attempts that exceed `PRAGMA busy_timeout = 5000;` return `SQLITE_BUSY`.
* **PostgreSQL Migration Triggers:** A transition to PostgreSQL is triggered if any of these operational thresholds are reached:
  1. Multi-user concurrent ingestion yields `SQLITE_BUSY` errors on $>5\%$ of write requests.
  2. Deployment scales to multiple application server nodes behind a load balancer.
  3. Stored document metadata and vector indices exceed 50 GB.

---

## 3. Two Distinct Deployment Modes

```
+--------------------------------------------------------------------------------------------------+
|                                    MODE 1: LOCAL RESEARCH MODE                                   |
|  - 100% On-Device Inference (Ollama Qwen 3.5 2B + SmolLM2)                                      |
|  - Dual Airgap Enforcement: Application Socket Guard + OS Windows Defender Firewall Rules       |
|  - Zero Outbound Public Network Egress; Zero Cloud API Keys Required                            |
+--------------------------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------------------------+
|                                    MODE 2: HOSTED PUBLIC MODE                                    |
|  - Public Reverse Proxy (HTTPS/TLS) with Authenticated Workspaces and CSRF Protection            |
|  - Controlled Cloud Model Inference (Explicitly Authorized Calls to Gemini, Groq, OpenRouter)    |
|  - Local Ollama Daemon strictly bound to 127.0.0.1 (Port 11434 NEVER publicly exposed)           |
|  - NOT described as airgapped due to authorized external AI API calls                            |
+--------------------------------------------------------------------------------------------------+
```

### 3.1 Local Research Mode Security
* **Purpose:** Academic research, sensitive internal documents, and faculty evaluations.
* **Network Restrictions:**
  1. **Application-Level Guard:** The `AdaptiveModelRouter` hard-disables all cloud adapters (`GeminiCloudAdapter`, `GroqCloudAdapter`, `OpenRouterCloudAdapter`).
  2. **OS-Level Firewall Guard:** Windows Defender Firewall rules block all outbound TCP traffic from the Python executable except to `127.0.0.1` and `::1`:
     ```powershell
     New-NetFirewallRule -DisplayName "SETU-NETRA-Airgap-Block" -Direction Outbound -Program (Get-Command python).Source -Action Block -RemoteAddress "Internet"
     ```
  3. **Verification:** Faculty auditors can independently verify zero non-loopback connections via PowerShell (`Get-NetTCPConnection`).

### 3.2 Hosted Public Mode Security
* **Purpose:** Public demonstration and collaborative multi-user research.
* **Boundaries:**
  1. The local Ollama daemon port (`11434`) is bound strictly to `127.0.0.1` and is unreachable from the public internet.
  2. Outbound HTTPS requests are permitted **only** to whitelisted cloud provider domains (`generativelanguage.googleapis.com`, `api.groq.com`, `openrouter.ai`).
  3. Document content is stored privately and partitioned by `workspace_id`.

---

## 4. Role-Based Access Control (RBAC) Matrix

The system defines four discrete user roles:
1. **`OWNER`:** Full administrative control, live routing weight tuning, hardware registry management, circuit breaker overrides, and security audit log inspection.
2. **`RESEARCHER`:** Full workspace capabilities, document ingestion, query execution, reasoning inspection, and research report generation.
3. **`FACULTY_OBSERVER`:** Read-only inspection across workspaces, live mathematical derivations, benchmark matrices, raw telemetry logs, and exportable audit traces. Cannot mutate data.
4. **`GUEST`:** Restricted to pre-loaded benchmark documents in the public sandbox. Rate-limited to 5 queries/minute, token generation capped at 256 tokens.

| Module & Capability | `GUEST` | `RESEARCHER` | `FACULTY_OBSERVER` | `OWNER` |
| :--- | :---: | :---: | :---: | :---: |
| **[A] Public Playground Query** | YES (Rate-limited) | YES | YES | YES |
| **[B] Document Upload & Extraction** | NO | YES | NO | YES |
| **[B] Workspace Creation & Deletion** | NO | YES | NO | YES |
| **[C] Pristine Document QA Canvas** | Read-Only (Demo) | YES | YES | YES |
| **[D] Knowledge Graph Exploration** | Read-Only (Demo) | YES | YES | YES |
| **[E] Spatial Provenance & Think Traces** | Read-Only (Demo) | YES | YES | YES |
| **[F] Report Studio & LaTeX Export** | NO | YES | Read-Only | YES |
| **[G] Model Daemon Controls** | NO | NO | NO | YES |
| **[H] Live Intelligence Map Stream** | YES (Filtered) | YES | YES | YES |
| **[I] The Well Fluid Capacity View** | YES | YES | YES | YES |
| **[J] Owner Canvas (Weight Sliders)** | NO | NO | NO | YES |
| **[J] Emergency Killswitch Trigger** | NO | NO | NO | YES |
| **[K] Live Mathematical Derivations** | NO | YES | YES | YES |
| **[K] Ground-Truth Matrix & NDJSON Export**| NO | NO | YES | YES |
| **[L] Audit Ledger & Security Log** | NO | NO | Read-Only | Full Access |

---

## 5. Cryptographic Identity & Session Management

### 5.1 Password Hashing with Argon2id
User authentication implements Argon2id conforming to RFC 9106 standards:
* **Algorithm:** Argon2id
* **Memory Cost ($m$):** $65,536 \text{ KiB}$ ($64 \text{ MB}$)
* **Time Cost ($t$):** $3$ iterations
* **Parallelism ($p$):** $4$ threads
* **Salt:** $16$ cryptographically secure random bytes generated via `secrets.token_bytes(16)`.

### 5.2 Session Lifecycle, Rotation & CSRF Protection
1. **Session Rotation:** Upon every successful login or role transition, the existing session ID is invalidated and a fresh 256-bit token is issued, preventing session fixation.
2. **Session Storage:** Only the SHA-256 digest of the token is stored in the database (`sessions.session_id_hash`).
3. **Cookie Attributes:**
   `Set-Cookie: setu_session=<token>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1; Max-Age=86400`
4. **Anti-CSRF Protection:** State-mutating requests (`POST`, `PUT`, `DELETE`) require a matching `X-CSRF-Token` header derived cryptographically from the active session.
5. **Session Revocation:** Calling `POST /api/v1/auth/logout` immediately deletes the session record from SQLite and wipes the client cookie.

---

## 6. Tamper-Evident Audit Ledger

All administrative actions, configuration changes, model invocations, and document access events are recorded in an append-only ledger (`audit_ledger`).

```
+--------------------------------------------------------------------------------------------------+
|                                    TAMPER-EVIDENT AUDIT CHAIN                                    |
|                                                                                                  |
|  [Entry N-1]                                [Entry N]                                            |
|  Hash: a4f8...                             Prev_Hash: a4f8...                                   |
|  Payload: Document Upload doc_01           Payload: Model Routing Rule Updated                  |
|                                            Hash = SHA256(Prev_Hash + Timestamp + Payload)        |
+--------------------------------------------------------------------------------------------------+
```

* **Tamper-Evident Property:** Any retroactive modification or deletion of an audit record breaks the SHA-256 hash chain of all subsequent entries.
* **Clarification:** This ledger is **tamper-evident** (cryptographically verifiable), not automatically immutable, because an operator with direct physical access to the SQLite file could recompute the chain if unmonitored. Independent external verification is achieved by exporting ledger hashes to the Faculty Observer Deck.
