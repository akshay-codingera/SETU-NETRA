# SETU-NETRA V2.0.0-RC1 — PHASE 2 ROLE-BASED ACCESS CONTROL (RBAC) MATRIX
**Role Taxonomy, Capability Mapping & Object-Level Workspace Boundaries**  
*Date: November 11, 2026*  

---

## 1. Role Taxonomy

SETU-NETRA establishes four discrete, mutually exclusive user roles in [`src/setu_netra/auth/roles.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/auth/roles.py):

| Role Identifier | Description & Institutional Mandate | Typical Identity |
|---|---|---|
| **`OWNER`** | System & Institutional Administrator. Full platform control, workspace lifecycle management, cross-tenant governance, audit trail verification, and user provisioning. | Lead System Engineer, Project Lead |
| **`RESEARCHER`** | Primary operational role. Performs document intelligence tasks: multi-page ingestion, OCR layout reconstruction, evidence-grounded queries, and personal workspace curation. Cannot modify system settings or delete other users' namespaces. | Research Scholar, Domain Scientist |
| **`FACULTY_OBSERVER`** | Institutional evaluator and audit authority. Possesses global **read-only** visibility across all workspaces, document indices, and audit chains for grading and review. Strictly blocked from mutating data or uploading documents. | Faculty Guide, External Invigilator, Auditor |
| **`GUEST`** | Unauthenticated or restricted visitor tier. Can view public documents and execute rate-limited, restricted queries. Strictly blocked from document ingestion, workspace creation, or session management. | Public Visitor, Demo Evaluator |

---

## 2. Granular Permissions Registry

| Permission Code | Category | Operational Scope |
|---|---|---|
| `platform:admin` | Administration | System-wide administrative operations and tenant governance. |
| `workspace:create` | Workspaces | Creating new isolated workspace namespaces. |
| `workspace:delete` | Workspaces | Deleting existing workspaces and cascading associated records. |
| `workspace:manage` | Workspaces | Updating workspace metadata, switching active workspaces, and managing memberships. |
| `document:upload` | Documents | Ingesting and vectorizing new PDF, DOCX, TXT, or raster image documents. |
| `document:read` | Documents | Inspecting document metadata, spatial bounding boxes, and retrieved passages. |
| `document:delete` | Documents | Deleting documents and associated pages and vector embeddings. |
| `query:execute` | Inference | Submitting unbounded queries to the intelligent routing engine and generative models. |
| `query:execute_restricted` | Inference | Submitting rate-limited queries restricted to pre-indexed extractive knowledge. |
| `conversation:manage` | Collaboration | Creating, updating, and deleting multi-turn conversation sessions. |
| `telemetry:observe` | Telemetry | Connecting to live Server-Sent Events (SSE) telemetry stream and inspecting worker health. |
| `audit:read` | Audit | Querying the tamper-evident audit ledger and running chain integrity checks. |
| `report:generate` | Reporting | Generating exportable research dossiers, evaluation metrics, and evidence summaries. |

---

## 3. Comprehensive Role-Permission Capability Matrix

| Permission | `OWNER` | `RESEARCHER` | `FACULTY_OBSERVER` | `GUEST` |
|---|:---:|:---:|:---:|:---:|
| `platform:admin` | **ALLOW** | DENY | DENY | DENY |
| `workspace:create` | **ALLOW** | **ALLOW** | DENY | DENY |
| `workspace:delete` | **ALLOW** | DENY | DENY | DENY |
| `workspace:manage` | **ALLOW** | **ALLOW** | DENY | DENY |
| `document:upload` | **ALLOW** | **ALLOW** | DENY | DENY |
| `document:read` | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| `document:delete` | **ALLOW** | **ALLOW** (Own Workspace) | DENY | DENY |
| `query:execute` | **ALLOW** | **ALLOW** | **ALLOW** | DENY |
| `query:execute_restricted` | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| `conversation:manage` | **ALLOW** | **ALLOW** | DENY | DENY |
| `telemetry:observe` | **ALLOW** | **ALLOW** | **ALLOW** | DENY |
| `audit:read` | **ALLOW** | DENY | **ALLOW** | DENY |
| `report:generate` | **ALLOW** | **ALLOW** | **ALLOW** | DENY |

---

## 4. Object-Level Workspace Boundaries (`verify_workspace_access`)

In addition to coarse role permissions, SETU-NETRA enforces object-level boundary verification on every document and workspace transaction via [`AuthService.verify_workspace_access()`](file:///d:/Projects/Setu-Netra/src/setu_netra/auth/service.py#L402):

```python
def verify_workspace_access(
    user_id: str,
    role: UserRole,
    workspace_id: str,
    require_write: bool = False,
) -> bool:
    # 1. OWNER has universal read/write access to all workspaces
    if role == UserRole.OWNER:
        return True

    # 2. FACULTY_OBSERVER has universal read access to all workspaces, but NEVER write
    if role == UserRole.FACULTY_OBSERVER:
        return not require_write

    # 3. All other roles require explicit membership in the target workspace
    cursor = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?;",
        (workspace_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        return False
    
    member_role = row[0]
    if require_write and member_role == "VIEWER":
        return False
        
    return True
```

### Boundary Enforcement Rules in Practice:
1. **Researcher Isolation:** Researcher A cannot list, view, retrieve, or delete documents belonging to Researcher B's workspace.
2. **Retrieval Exclusion:** When Researcher B asks a question, the vector similarity engine strictly filters out blocks belonging to Researcher A's workspace before scoring.
3. **Faculty Audit Privilege:** A Faculty Observer can query any document across the institution to verify factual accuracy and citations, but cannot delete or tamper with researchers' records.
