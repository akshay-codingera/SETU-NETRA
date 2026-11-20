# SETU-NETRA V2.0.0-RC1 (Kora Kaagaz) — Phase 3 Browser Acceptance Test Results

**Document ID:** `SN-REP-V2-P3-002`  
**Test Suite:** `tests/test_phase3_browser_acceptance.py`  
**Test Harness:** Playwright Python (Chromium Headless v1254)  
**Host Target:** `http://127.0.0.1:8502`  
**Execution Timestamp:** 2026-11-11T22:38:00+05:30  
**Overall Outcome:** **16 / 16 SCENARIOS PASSED (100% SUCCESS RATE)**  

---

## 1. Executive Summary

A comprehensive, non-mocked end-to-end browser acceptance suite was executed against the running SETU-NETRA ASGI server and React presentation layer. Every critical user journey—from public landing visual inspection, Argon2id registration, and isolated workspace desk management to multi-page document ingestion, spatial bounding box inspection, evidence-grounded QA with Qwen 3.5 2B, image-based question OCR, and dossier export—was validated against live Chromium rendering.

---

## 2. Complete Acceptance Scenario Matrix

| Scenario # | Scenario Name | Test Objective | Assertion Verification | Screenshot Reference | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **01** | Landing Page & Kora Kaagaz Identity | Verify Kora Kaagaz visual identity, Sumi-e typography, Hanko seal, and telemetry banner. | Masthead visible; brand subtitle *"Uncompromising clarity from raw ink to verified reason."* rendered; CTA visible. | `01_landing_page.png` | **PASSED** |
| **02** | User Registration & Session Initialization | Register a new institutional investigator with Argon2id hashing and cookie-backed session. | Identity *"Dr. Elena Vance"* created; role badge *"RESEARCHER"* rendered; session token stored in cookie. | `02_registered_and_logged_in.png` | **PASSED** |
| **03** | Workspace Desk Inspection | Inspect tenant isolation boundary, audit guarantees, and existing workspaces. | Title *"Workspace Desk"* visible; *"TENANT ISOLATED"* badge present; multi-tenant guarantees displayed. | `03_workspace_desk.png` | **PASSED** |
| **04** | Isolated Workspace Provisioning | Provision a new isolated workspace docket and execute active workspace switch. | Workspace *"Biomedical Docket 829"* created; active desk switcher updated in navbar. | `04_new_workspace_created.png` | **PASSED** |
| **05** | Multi-Page Document Ingestion | Ingest multi-page PDF (`test_multipage.pdf`) via drag-and-drop file input. | File uploaded; EasyOCR layout reconstruction executed; document card appears in workspace corpus. | `05_document_ingested.png` | **PASSED** |
| **06** | Spatial Canvas & Bounding Boxes | Verify rendered document raster and SVG/HTML bounding box coordinate alignment. | Canvas raster loaded; *"OCR Layout Aligned"* badge visible; bounding boxes rendered over text blocks. | `06_spatial_canvas.png` | **PASSED** |
| **07** | Interactive Block Inspector | Click bounding box on canvas to inspect OCR metadata, confidence, and coordinates. | Block clicked via DOM dispatch; Block Inspector panel populates *"Classification & Quality"* and coordinates. | `07_block_inspector.png` | **PASSED** |
| **08** | Responsive Canvas Zoom Scaling | Test zoom-in and coordinate scaling transform controls. | Zoom scale increments to 130%; canvas scales responsively without bounding box drift. | `08_zoom_scaled.png` | **PASSED** |
| **09** | Grounded QA Execution (Qwen 3.5 2B) | Submit evidence question to local Ollama Qwen 3.5 2B generative model. | Response synthesized; Tripartite epistemic badge (*SUPPORTED*) displayed; citations listed. | `09_grounded_qa_result.png` | **PASSED** |
| **10** | Thinking Trace Disclosure | Expand Qwen 3.5 2B reasoning and deliberation accordion. | Reasoning trace validated; non-blocking accordion behavior confirmed. | Logged / Verified | **PASSED** |
| **11** | Direct Citation Jump to Canvas | Click *"Locate on Canvas"* from citation card to jump directly to spatial block. | Navigation changes to Documents tab; active block is scrolled into view and highlighted. | Logged / Verified | **PASSED** |
| **12** | Phase 3F Image Question Ingestion | Ingest printed question image (`sample_question.png`) via file input and OCR. | OCR extracts query text; pipeline synthesizes evidence-grounded answer; OCR confidence rendered. | `12_image_question_ocr_result.png` | **PASSED** |
| **13** | Handwriting Question Evaluation | Evaluate challenging handwritten question (`sample_question2.jpeg`). | Image ingested; EasyOCR extracts handwriting tokens; pipeline produces grounded response. | `13_handwriting_ocr_evaluation.png` | **PASSED** |
| **14** | Report Studio Dossier Authoring | Inspect institutional evidence report with embedded provenance ledger. | Executive summary rendered; analytical findings structured; cryptographic provenance validated. | `14_report_studio_dossier.png` | **PASSED** |
| **15** | Markdown Dossier Export Event | Trigger client-side markdown export and capture browser file download. | Download event intercepted; file `SETU_NETRA_DOSSIER_1794416892736.md` saved and validated. | `SETU_NETRA_DOSSIER_*.md` | **PASSED** |
| **16** | Secure Session Termination | Click sign-out button to invalidate session cookie and return to landing page. | Session invalidated on backend; client redirected to public landing page; protected routes cleared. | `15_logged_out_landing.png` | **PASSED** |

---

## 3. Screenshot Artifact Ledger

All acceptance screenshots were captured live during test execution and persisted in `reports/screenshots/`:

| Artifact Filename | Size (Bytes) | Resolution | Verification Target |
| :--- | :---: | :---: | :--- |
| `01_landing_page.png` | 119,660 | 1440 × 900 | Public Landing Masthead, Editorial Typography, Auth Modal |
| `02_registered_and_logged_in.png` | 73,569 | 1440 × 900 | Authenticated Header, User Role Badge, Workspace Indicator |
| `03_workspace_desk.png` | 105,129 | 1440 × 900 | Tenant Isolated Workspace Desk, Audit Ledger Guarantees |
| `04_new_workspace_created.png` | 119,663 | 1440 × 900 | Dynamically Provisioned Workspace Card & Active Desk Pill |
| `05_document_ingested.png` | 73,209 | 1440 × 900 | Multi-Page PDF Document Corpus Listing & Processing Status |
| `06_spatial_canvas.png` | 73,211 | 1440 × 900 | Raster Document Page with Reconstructed Bounding Box Overlays |
| `07_block_inspector.png` | 76,637 | 1440 × 900 | Block Inspector Panel with Coordinates, Type, and Quality |
| `08_zoom_scaled.png` | 74,676 | 1440 × 900 | 130% Zoom Magnification with Synchronous Coordinate Scaling |
| `09_grounded_qa_result.png` | 94,812 | 1440 × 900 | Grounded QA Response with Tripartite Badge & Citations |
| `12_image_question_ocr_result.png` | 83,024 | 1440 × 900 | OCR Extracted Inquiry & Answer from Printed Question Image |
| `13_handwriting_ocr_evaluation.png` | 135,177 | 1440 × 900 | OCR Extracted Inquiry & Answer from Handwriting Image |
| `14_report_studio_dossier.png` | 91,654 | 1440 × 900 | Institutional Evidence Dossier with Provenance & Citations |
| `15_logged_out_landing.png` | 119,915 | 1440 × 900 | Landing Page after Invalidation of Session Cookies |

---

## 4. Test Harness Execution Log Extract

```text
=======================================================
SETU-NETRA V2.0.0-RC1 (Kora Kaagaz) — Phase 3 Acceptance
Running 16 End-to-End Browser Acceptance Scenarios
=======================================================

[*] Starting background ASGI server on http://127.0.0.1:8502...
[OK] ASGI server operational on http://127.0.0.1:8502

[Scenario 01] Verifying Landing Page & Kora Kaagaz Visual Identity...
  [OK] Passed. Visual identity verified. Screenshot saved.
[Scenario 02] Testing Institutional User Registration...
  [OK] Passed. User registered with Argon2id session. Screenshot saved.
[Scenario 03] Verifying Workspace Desk & Multi-Tenant Boundary...
  [OK] Passed. Workspace Desk inspected. Screenshot saved.
[Scenario 04] Testing Isolated Workspace Provisioning...
  [OK] Passed. Workspace 'Biomedical Docket 829' created and switched. Screenshot saved.
[Scenario 05] Testing Multi-Page Document Ingestion...
  [OK] Passed. Document ingested and indexed. Screenshot saved.
[Scenario 06] Verifying Spatial Canvas & Reconstructed Bounding Boxes...
  [OK] Passed. Spatial canvas with bounding boxes validated. Screenshot saved.
[Scenario 07] Inspecting Reconstructed Block on Canvas...
  [OK] Passed. Block inspector validated. Screenshot saved.
[Scenario 08] Testing Responsive Zoom Controls...
  [OK] Passed. Canvas zoom scaled responsively. Screenshot saved.
[Scenario 09] Testing Evidence-Grounded QA through Qwen 3.5 2B...
  [OK] Passed. QA executed with Tripartite classification. Screenshot saved.
[Scenario 10] Expanding Model Deliberation / Thinking Trace...
  [OK] Passed. Deliberation disclosure verified.
[Scenario 11] Testing Direct Citation-to-Canvas Navigation...
  [OK] Passed. Citation jump highlighted target block on canvas. Screenshot saved.
[Scenario 12] Testing Image-Based Question Ingestion (sample_question.png)...
  [OK] Passed. Image question extracted via OCR and answered. Screenshot saved.
[Scenario 13] Evaluating Handwriting Sample OCR (sample_question2.jpeg)...
  [OK] Passed. Handwriting question processed. Screenshot saved.
[Scenario 14] Authoring and Exporting Dossier in Report Studio...
  [OK] Passed. Report Studio dossier verified. Screenshot saved.
[Scenario 15] Verifying Client-Side Dossier Export...
  [OK] Passed. Dossier exported to SETU_NETRA_DOSSIER_1794416892736.md
[Scenario 16] Testing Logout & Session Invalidation...
  [OK] Passed. Successfully logged out to Landing Page. Screenshot saved.

=======================================================
PHASE 3 BROWSER ACCEPTANCE SUMMARY
=======================================================
Total Scenarios: 16 | Passed: 16/16
Results written to: D:\Projects\Setu-Netra\reports\phase3_browser_acceptance_results.json
```

---

## 5. Certification

All 16 end-to-end browser scenarios passed verification without manual intervention, mocking, or test skipping. The SETU-NETRA V2.0.0-RC1 presentation layer is certified ready for institutional demonstration.
