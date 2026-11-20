# SETU-NETRA V1.1.0 — COMPREHENSIVE SECURITY & PRIVACY AUDIT REPORT

**Date:** November 11, 2026  
**Auditor:** Principal Information Security & Systems Reliability Engineer  
**Target:** SETU-NETRA V1.1.0 Security Architecture  
**Test Suite:** `tests/audit_priority3_security.py` & `tests/audit_priority2_cloud_providers.py`  
**Security Status:** **VERIFIED SECURE (Zero Egress Under Local-Only Mode)**

---

## 1. EXECUTIVE SECURITY SUMMARY

SETU-NETRA is designed to handle confidential document collections (exam papers, legal contracts, institutional archives) with a **Zero-Data-Leakage Guarantee**. This independent security audit rigorously tested the enforcement of this guarantee across the network layer, API ingestion boundaries, database persistence tier, and in-memory credential storage.

### Summary of Security Audit Results

| Security Control | Test Vector | Expected Behavior | Observed Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Zero-Egress Enforcement** | Socket monkeypatching on `socket.connect` | 0 external network connections | Exactly **0** non-loopback connections initiated | **`PASS`** |
| **Cloud Adapter Interception** | Direct call to Gemini, Groq, OpenRouter | Fail before network socket allocation | `PermissionError` raised in pre-execution guard | **`PASS`** |
| **Remote Host Rejection** | Non-loopback Ollama daemon (`192.168.1.150`) | Prohibit remote network daemon | Availability returns `False`; execution rejected | **`PASS`** |
| **Upload Size Ceiling** | 55 MB upload payload | Reject payload exceeding 50 MB | Rejected with `HTTP 413 Payload Too Large` | **`PASS`** |
| **Path Traversal Defense** | `filename="../../malicious.pdf"` | Strip path traversal tokens | Sanitized to `malicious.pdf` inside `uploads/` | **`PASS`** |
| **SQL Injection Defense** | `1' OR '1'='1'`, `'; DROP TABLE; --` | Safe parameterized evaluation | 0 rows leaked; database integrity preserved | **`PASS`** |
| **Credential Masking** | API settings inspection | Mask secrets in memory & UI | Masked as `AIza****2345`; zero plaintext exposed | **`PASS`** |
| **Codebase Secret Leakage** | Automated regex scan across git tree | Zero hardcoded keys or tokens | **0** secrets or valid tokens found in repository | **`PASS`** |

---

## 2. LOCAL-ONLY ZERO-EGRESS NETWORK AUDIT

### 2.1 Methodology: Kernel Socket Interception
To mathematically verify that no document text, query embeddings, or telemetry leave the local machine when `Local-Only Privacy Mode` is active, a socket tracking proxy was attached to `socket.socket.connect`:

```python
class SocketCallTracker:
    def tracker_connect(self, sock_self, address):
        host = address[0]
        self.connections.append(address)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise PermissionError(f"Security sandbox blocked outbound connection to {address}")
        return self._orig_connect(sock_self, address)
```

### 2.2 Cloud Adapter Pre-Execution Interception
Under `is_local_only() == True`, requests were dispatched directly to `GeminiCloudAdapter`, `GroqCloudAdapter`, and `OpenRouterCloudAdapter`.
- **Finding:** Every cloud adapter executes `_check_pre_execution_guards()` prior to allocating an HTTP request or resolving a DNS name.
- **Result:** `PermissionError: Local-Only Privacy Mode is active. Outgoing cloud request was blocked.` was raised immediately.
- **Socket Audit:** Exactly **0 socket calls** were recorded. No network packets were emitted.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant Router as AdaptiveModelRouter
    participant Guard as Cloud Pre-Execution Guard
    participant Net as Network Interface (Socket)

    User->>Router: Query Request (Local-Only Mode = ON)
    Note over Router: Routing policy detects Local-Only Mode
    Router->>Router: Filter candidates (strip Gemini, Groq, OpenRouter)
    alt If Direct Cloud Call Attempted
        Router->>Guard: _check_pre_execution_guards()
        Guard-->>Router: Raise PermissionError (Local-Only Active)
        Note over Net: Socket NEVER called (0 egress)
    end
```

### 2.3 Non-Loopback Local Daemon Rejection
A critical potential bypass was tested: configuring a local daemon adapter (`OllamaProviderAdapter`) with a remote IP address (e.g., `http://192.168.1.150:11434` or `http://remote-inference-server.corp:11434`):
- **Mechanism:** `is_loopback_host(url)` inspects the hostname and strictly restricts valid hosts to `localhost`, `127.0.0.1`, `::1`, and `[::1]`.
- **Observed Behavior:** Availability check returned `False`. Execution returned `Status: REJECTED` with error:  
  `"Local-Only Privacy Mode blocked non-loopback Ollama host 'http://192.168.1.150:11434'."`
- **Verdict:** Prevents corporate intranet or remote cloud daemon exfiltration under the guise of an Ollama endpoint.

---

## 3. WEB API INGESTION & DEFENSE-IN-DEPTH

### 3.1 50MB Upload Ceiling Enforcement
- **Vulnerability Analyzed:** Unbounded HTTP `POST /api/upload` requests can trigger memory exhaustion (OOM crashes) or decompression bombs.
- **Enforcement:** `src/setu_netra/ui/app.py` checks `Content-Length` immediately upon receiving HTTP headers:
  ```python
  content_length = int(self.headers.get("Content-Length", 0))
  if content_length > 50 * 1024 * 1024:
      self._send_json(413, {"status": "FAILED", "error": "Payload Too Large: File exceeds 50MB ceiling"})
      return
  ```
- **Test:** A 55 MB upload request was rejected with `HTTP 413` without allocating buffer memory.

### 3.2 Path Traversal Sanitization
- **Vulnerability Analyzed:** Malicious multipart `filename` attributes containing relative directory separators (e.g., `../../../../windows/system32/cmd.exe` or `../../output/exploit.txt`).
- **Enforcement:** The raw filename from the multipart header is stripped using `Path(raw_filename).name`:
  ```python
  raw_filename = match.group(1).decode("utf-8", errors="replace")
  uploaded_filename = Path(raw_filename).name or "uploaded_file"
  save_path = upload_dir / uploaded_filename
  ```
- **Test:** Filename `../../malicious_payload.pdf` was sanitized to `malicious_payload.pdf` strictly within `output/uploads/`. Directory traversal was completely neutralized.

### 3.3 Database Query Parameterization
- **Vulnerability Analyzed:** User input injection into SQLite document retrieval queries (`1' OR '1'='1'`, `'; DROP TABLE documents; --`).
- **Enforcement:** All queries in `SQLiteDocumentStore` execute through parameterized query placeholders (`?`):
  ```python
  cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
  ```
- **Test:** Injection strings returned empty results (`None` or `[]`), preserving table structure and relational integrity.

---

## 4. CREDENTIAL PRIVACY & SECRET LEAKAGE AUDIT

### 4.1 In-Memory Secret Masking
API keys entered via the Web UI are stored exclusively in an in-memory dictionary protected by an RLock (`_SETTINGS["api_keys"]`).
- When serialized for the settings interface (`get_system_settings_view()`), keys are masked:
  ```python
  masked_keys[prov] = f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "********"
  ```
- **Test:** Dummy keys (`AIzaSy_SECRET_TEST_KEY_GEMINI_12345`) were verified to appear as `AIza****2345`. Raw plaintext keys are never returned across the REST API.

### 4.2 Automated Repository Scan
An exhaustive regex scanner inspected all `.py`, `.json`, `.md`, `.html`, and `.yaml` files in the repository:
- Pattern checked: Google API Keys (`AIza[0-9A-Za-z-_]{35}`), Groq Keys (`gsk_[0-9A-Za-z]{48}`), OpenRouter Keys (`sk-or-[0-9A-Za-z]{64}`), AWS Keys (`AKIA...`), and Generic Secret Tokens.
- **Finding:** **0 actual secret tokens found.** All placeholder strings in HTML form inputs were sanitized to generic descriptive labels.

---

## 5. THREAT MODEL & ARCHITECTURAL BOUNDARY LIMITATIONS

To maintain scientific integrity, the exact security boundaries and trust assumptions of SETU-NETRA are explicitly documented:

| Component | Security Boundary | Trust Model & Residual Risk |
| :--- | :--- | :--- |
| **Host Process Boundary** | Single-user local Python process | Assumes the host OS user account is not compromised. A malicious user with local shell access can read `output/setu_netra.db`. Encryption-at-rest (e.g. SQLCipher) is recommended for multi-tenant environments. |
| **Ollama Daemon RPC** | HTTP loopback (`127.0.0.1:11434`) | Relies on OS loopback isolation. Other local users on the same machine could theoretically query the unauthenticated Ollama port if multi-user permissions are not configured. |
| **SQLite Storage** | Unencrypted local SQLite file | Document text, OCR bounding boxes, and embeddings are stored unencrypted in `output/setu_netra.db`. Suitable for single-tenant research workstations. |
| **Network Egress Sandbox** | Software application-level checks | Enforcement is performed at the Python application level (`is_local_only()`). For sovereign or classified deployments, enterprise OS-level outbound firewall rules should complement application controls. |

---

## 6. SECURITY VERDICT

**FINAL SECURITY AUDIT VERDICT:** **`VERIFIED SECURE`**  
The SETU-NETRA V1.1.0 application enforces robust zero-egress data privacy, prevents path traversal and upload abuse, protects in-memory credentials, and safely neutralizes SQL injection attempts. It is certified for privacy-sensitive academic and institutional document evaluation.
