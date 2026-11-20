# SETU-NETRA Version 1.0 — Limitation and Risk Register

**Author:** Independent AI Systems Researcher & Statistical Reviewer  
**Project:** SETU-NETRA (Intelligent Document Understanding, Evidence-Grounded Question Answering, and Adaptive AI Model Orchestration)  
**Status:** Version 1.0 Post-Acceptance Comprehensive Risk Audit (Revision 2 — Methodological Review)  
**Date:** November 2026  
**Scope:** Identification, categorization, severity assessment, and mitigation pathways for technical, architectural, performance, security, and research risks.

---

## Executive Summary

Engineering maturity requires transparently identifying system boundaries, potential failure points, and methodological limitations. While **SETU-NETRA Version 1.0** successfully demonstrates a functional, 173-test-verified vertical slice, several critical risks span the codebase. These include single-writer database serialization, lack of vector indexing, thread oversubscription on CPU, heuristic coreference rewriting, uncalibrated epistemic abstention, and unverified cloud production credentials.

This Risk Register documents and scores every known vulnerability, boundary limitation, and research threat across the platform. Each risk is evaluated using a quantitative **Risk Priority Number (RPN)** framework ($\text{RPN} = \text{Severity} \times \text{Likelihood} \times \text{Detectability}$) and assigned concrete, actionable engineering mitigations for Version 1.1. In this revised edition, all previous overclaims regarding zero hallucination, zero memory swapping, and unverified latency reductions have been formally eliminated.

---

## Risk Scoring Methodology

- **Severity ($S \in [1, 5]$):** 1 = Negligible cosmetic flaw; 3 = Moderate degradation or false result; 5 = Total system crash, data loss, or privacy breach.
- **Likelihood ($L \in [1, 5]$):** 1 = Rare edge case; 3 = Occurs under moderate concurrent load; 5 = Inevitable in standard operation.
- **Detectability ($D \in [1, 5]$):** 1 = Instantly detected by runtime checks/tests; 3 = Silent degradation noticed during deep inspection; 5 = Completely undetectable without external audit.
- **Risk Priority Number ($\text{RPN} = S \times L \times D \in [1, 125]$):**
  - **Critical ($\text{RPN} \ge 60$):** P0 blocker requiring immediate architectural remediation.
  - **High ($36 \le \text{RPN} < 60$):** P1 engineering priority before multi-user deployment.
  - **Medium ($16 \le \text{RPN} < 36$):** P2 functional or performance improvement.
  - **Low ($\text{RPN} < 16$):** Minor cosmetic or edge-case limitation.

---

## Deep Dive on Core Risk Vectors

### Vector 1: Small Benchmark Sample Sizes & Statistical Power Deficits
- **Vulnerability:** Early development milestones (Stages 1–5) and initial unit tests evaluated retrieval accuracy and scheduler throughput on micro-samples of $N = 10$ to $N = 20$ queries or single-document synthetic files.
- **Risk Manifestation:** Small sample sizes yield wide confidence intervals, high empirical variance, and susceptibility to random seed bias. A metric measured on 20 queries has wide binomial confidence intervals, making comparative claims against baselines statistically invalid.
- **Severity:** 3 | **Likelihood:** 4 | **Detectability:** 3 | **RPN:** 36 (High)
- **Concrete Mitigation:** Enforce the Version 1.1 Experimental Protocol: minimum $N \ge 128$ queries for retrieval evaluations to achieve power $1 - \beta \ge 0.80$ at $\alpha = 0.05$ for small-to-medium effect sizes ($d = 0.25$). Mandate reporting 95% confidence intervals and p-values.

---

### Vector 2: Synthetic versus Real-World Ingestion Workloads
- **Vulnerability:** Automated acceptance test suites generate clean synthetic text files (e.g. `demo_os_lecture.txt`) or pristine digital PDFs. Real-world documents contain low-resolution phone camera scans, perspective distortion, non-standard fonts, watermarks, coffee stains, crumpled paper, and non-horizontal text lines.
- **Risk Manifestation:**
  - `EasyOCR` character error rate (CER) increases drastically on degraded scans (from $<2\%$ on synthetic prints to $>25\%$ on low-contrast mobile captures).
  - `RecursiveXYCut` completely collapses when text lines have a 3-degree skew angle, because whitespace projection valleys disappear, merging unrelated columns into a single illegible block.
- **Severity:** 4 | **Likelihood:** 4 | **Detectability:** 2 | **RPN:** 32 (Medium)
- **Concrete Mitigation:** Integrate an automated pre-OCR image rectification pipeline in `src/setu_netra/preprocessing/`: deskewing via Hough transform, adaptive Otsu binarization, and contrast normalization before passing images to `EasyOCREngine`.

---

### Vector 3: Retrieval Evaluation Granularity & Spatial Edge Cases
- **Vulnerability:** `DocumentRetriever` operates strictly at the granularity of discrete `DocumentBlock` entities produced by `RecursiveXYCut`.
- **Risk Manifestation:**
  - **Boundary Splitting:** If an essential factual proposition spans across two pages or two column blocks (e.g. the first half of a sentence is at the bottom of Page 1 and the second half is at the top of Page 2), the two halves are stored as separate blocks. Neither block contains the complete proposition, causing dense similarity to fail.
  - **Overlapping Bounding Boxes:** Multi-column layouts with floating figures or callout boxes frequently generate overlapping bounding-box coordinates in SQLite, causing ambiguous visual highlighting in the web UI.
- **Severity:** 3 | **Likelihood:** 3 | **Detectability:** 3 | **RPN:** 27 (Medium)
- **Concrete Mitigation:** Implement cross-block sliding window context merging (concatenating block $i$ with adjacent blocks $i-1$ and $i+1$ with boundary overlap markers during context synthesis).

---

### Vector 4: Citation Correctness & Token-Overlap Verification Limitations
- **Vulnerability:** `CitationVerifier` parses citations using a strict regular expression:
  $$\texttt{\textbackslash[Doc:\textbackslash s*(?P<doc>[\^{},\textbackslash]]+),\textbackslash s*Page:\textbackslash s*(?P<page>\textbackslash d+),\textbackslash s*Block:\textbackslash s*(?P<block>\textbackslash d+)\textbackslash]}$$
  and verifies grounding via bag-of-words token overlap ($35\%$ threshold).
- **Risk Manifestation:**
  - **Syntax Mutation False Negatives:** If a generative model alters the citation syntax (e.g. writing `[Document: os_lecture.txt, p. 2, b. 4]` or `[Doc: 1, Page: 2]`), the regex fails to match. The verifier concludes zero citations were attempted and flags the answer as `GENERAL_KNOWLEDGE` or `UNSUPPORTED`, even when the factual assertion was accurate.
  - **Negation & Contradiction Blindness:** Word overlap ignores polarity words. If a passage states *"The cache does not invalidate lines on write-through"* and the model asserts *"The cache invalidates lines on write-through"*, token overlap is $\approx 85\%$. The verifier falsely assigns `EVIDENCE_BACKED`, certifying a complete factual contradiction.
  - **Semantic Antonymy:** Word overlap cannot differentiate opposite numeric or adjective assertions (e.g., "latency increased to 100ms" vs "latency decreased to 100ms").
- **Severity:** 4 | **Likelihood:** 4 | **Detectability:** 4 | **RPN:** 64 (Critical)
- **Concrete Mitigation:** Upgrade `CitationVerifier` to use flexible multi-pattern regex matching and replace simple bag-of-words token overlap with an ONNX-quantized lightweight Natural Language Inference (NLI) model (e.g. `cross-encoder/nli-deberta-v3-small`) to verify directional textual entailment.

---

### Vector 5: Hallucination and Abstention Under Model Pressure
- **Vulnerability:** Local Small Language Models (`HuggingFaceTB/SmolLM2-135M-Instruct`) have only 135 million parameters. They have limited parameter capacity to resist sycophancy or follow complex negative constraints.
- **Risk Manifestation:**
  - When prompted with context that does not contain the answer, SmolLM2 frequently attempts to answer anyway using ungrounded pre-training weights, or confabulates plausible-sounding technical text rather than outputting explicit abstention phrases.
  - The model has a low attention horizon on CPU, and long context windows (>1,000 tokens) cause attention dilution, leading the model to hallucinate facts from earlier paragraphs.
- **Severity:** 4 | **Likelihood:** 4 | **Detectability:** 3 | **RPN:** 48 (High)
- **Concrete Mitigation:** Enforce Tier-1 routing policy: factual questions default strictly to bounded Extractive QA. For generative tasks, apply logit bias or strict structured JSON schema output forcing explicit boolean evidence-support flags.

---

### Vector 6: SQLite Concurrency and Serialization Bottlenecks
- **Vulnerability:** The document store relies on a single SQLite database file (`output/setu_netra.db`). While WAL mode allows concurrent readers, **writes are serialized via an exclusive database lock**.
- **Risk Manifestation:**
  - Under concurrent multi-user load, simultaneous document ingestion (`store.store_document`), vector writing (`store.store_embeddings`), and conversation message logging (`store.add_message`) compete for the exclusive write lock.
  - If a large document write transaction takes $500\,\text{ms}$, incoming message inserts throw `sqlite3.OperationalError: database is locked`.
  - In addition, SQLite lacks a vector index, requiring full table scans loading all embedding BLOBs into Python memory on every query.
- **Severity:** 4 | **Likelihood:** 4 | **Detectability:** 2 | **RPN:** 32 (Medium)
- **Concrete Mitigation:** Configure `sqlite3.connect(timeout=30.0)`, isolate conversation history into a separate SQLite database file (`conversations.db`) from the document store (`documents.db`), and introduce an in-memory FAISS or SQLite-VSS vector index.

---

### Vector 7: CPU Contention and Physical RAM Paging Realities
- **Vulnerability:** Target hardware is a standard developer workstation with **16 GB RAM and 4–8 CPU cores**.
- **Risk Manifestation:**
  - Concurrent execution of EasyOCR (PyTorch CRAFT + CRNN, $\approx 1.2\,\text{GB}$ RAM), SmolLM2-135M ($\approx 600\,\text{MB}$ RAM), MiniLM ($\approx 350\,\text{MB}$ RAM), and document matrices causes physical RAM consumption to approach $85\%$.
  - Thread oversubscription: PyTorch defaults to spawning OpenMP threads matching physical CPU cores. When 4 worker threads run inference simultaneously, $4 \times 8 = 32$ threads compete for 8 CPU cores. This causes cache thrashing, context switching overhead, and latency inflation.
  - **Memory Projection vs Paging Realities:** A projected steady-state usage of $\approx 7.4\,\text{GB}$ does **not guarantee zero swapping**. In Windows 11, the memory manager dynamically trims process working sets, pages out inactive libraries, and responds to background OS services (e.g. Windows Defender). Swapping can occur during sudden memory allocations unless pages are pinned via OS-level memory locking.
- **Severity:** 4 | **Likelihood:** 4 | **Detectability:** 3 | **RPN:** 48 (High)
- **Concrete Mitigation:** Pin PyTorch CPU threads globally via `torch.set_num_threads(2)`, enforce strict worker pool concurrency limits ($C_{\max} = 2$ active tensor workers), and utilize 8-bit quantized weights (`bitsandbytes` or ONNX Runtime).

---

### Vector 8: Absence of Cross-Document Contradiction Detection
- **Vulnerability:** When a multi-document repository contains conflicting factual propositions across documents (e.g. Doc A specifying a 50ms heartbeat and Doc B specifying 120ms), the system merely ranks passages by hybrid score.
- **Risk Manifestation:**
  - Whichever passage scores slightly higher is returned as an authoritative truth.
  - The system exhibits zero contradiction awareness, fails to arbitrate conflicting sources, and does not notify the user of contradiction.
  - The answer is classified as `EVIDENCE_BACKED` because it matches the cited top passage, concealing the disagreement.
- **Severity:** 4 | **Likelihood:** 3 | **Detectability:** 3 | **RPN:** 36 (High)
- **Concrete Mitigation:** In Version 1.1, introduce a pairwise NLI contradiction classifier across retrieved candidate passages from different documents, flagging contradictory assertions and presenting multi-source attribution in the UI.

---

### Vector 9: ReLU Score Rectification Side Effects on Ranking and Ties
- **Vulnerability:** In `DocumentRetriever`, dense cosine scores are clipped via:
  $$S_{\text{rect}} = \max(0.0, \min(1.0, S_{\text{raw}}))$$
- **Risk Manifestation:**
  - All negative cosine similarities are mapped to $0.0$, creating artificial rank ties among negative candidates and discarding negative discriminability.
  - In hybrid fusion $S_{\text{hybrid}} = \alpha S_{\text{rect}} + (1 - \alpha) S_{\text{lex}}$, semantically contradictory passages ($S_{\text{raw}} = -0.70$) that share common keywords are not penalized, allowing spurious lexical overlap to elevate them into the top-$k$ results.
- **Severity:** 3 | **Likelihood:** 3 | **Detectability:** 2 | **RPN:** 18 (Medium)
- **Concrete Mitigation:** Evaluate true BM25 retrieval with Reciprocal Rank Fusion (RRF) and affine normalization ($S_{\text{affine}} = \frac{S_{\text{raw}} + 1}{2}$) to replace hard ReLU clipping in Version 1.1.

---

### Vector 10: Privacy and Data Governance Vulnerabilities
- **Vulnerability:** Enterprise and academic documents frequently contain Personally Identifiable Information (PII), proprietary algorithms, student grades, or protected research data.
- **Risk Manifestation:**
  - Inadvertent data leakage: If Local-Only Privacy Mode is accidentally disabled or misconfigured, document text and queries could be transmitted to external cloud APIs (Google Gemini, Groq, OpenRouter).
  - Unencrypted At-Rest Storage: SQLite stores plain-text document paragraphs, user chat queries, and system responses unencrypted on disk in `output/setu_netra.db`.
- **Severity:** 5 | **Likelihood:** 2 | **Detectability:** 2 | **RPN:** 20 (Medium)
- **Concrete Mitigation:** Local-Only Privacy Mode is hardcoded to fail-safe default (`SETU_NETRA_LOCAL_ONLY=1`); add a pre-socket outbound network firewall hook intercepting any HTTP request to external domains when privacy mode is active; explore SQLite database encryption via SQLCipher.

---

## Comprehensive Quantitative Risk Matrix

| Risk ID | Category | Risk Description | Severity ($S$) | Likelihood ($L$) | Detectability ($D$) | RPN | Risk Tier | Concrete Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Research | Small benchmark sample sizes ($N < 50$) leading to invalid statistical claims | 3 | 4 | 3 | **36** | High | Scale test suites to $N \ge 128$ queries; mandate 95% CIs and p-values |
| **RSK-02** | Vision | XY-Cut projection collapse on skewed scans or complex non-rectangular layouts | 4 | 4 | 2 | **32** | Medium | Add deskewing via Hough transform and adaptive Otsu binarization |
| **RSK-03** | Retrieval | Boundary splitting across pages causing facts to be severed into separate blocks | 3 | 3 | 3 | **27** | Medium | Implement sliding-window context stitching across adjacent blocks |
| **RSK-04** | QA / Trust | Citation regex fragility and token overlap false-positive on negated facts | 4 | 4 | 4 | **64** | **Critical** | Flexible multi-syntax regex + ONNX-quantized NLI textual entailment |
| **RSK-05** | Modeling | Small SLM (SmolLM2-135M) hallucinating when facts are missing from context | 4 | 4 | 3 | **48** | High | Route factual queries to extractive QA; force structured JSON abstention |
| **RSK-06** | Database | SQLite write lock contention causing `database is locked` during concurrent chat | 4 | 4 | 2 | **32** | Medium | Increase busy timeout (30s); separate `conversations.db` from `documents.db` |
| **RSK-07** | Hardware | Thread oversubscription and RAM swapping on 16 GB workstation under load | 4 | 4 | 3 | **48** | High | Pin `torch.set_num_threads(2)`; clamp worker concurrency; INT8 quantization |
| **RSK-08** | QA / Logic | Complete absence of cross-document contradiction detection and arbitration | 4 | 3 | 3 | **36** | High | Introduce pairwise NLI contradiction classifier across retrieved passages |
| **RSK-09** | Retrieval | ReLU score clipping creating rank ties at 0.0 and suppressing negative penalty | 3 | 3 | 2 | **18** | Medium | Evaluate affine normalization and Reciprocal Rank Fusion (RRF) |
| **RSK-10** | Security | Unencrypted plain-text document blocks and chat history stored in SQLite | 5 | 2 | 2 | **20** | Medium | Fail-safe local-only privacy enforcement; evaluate SQLCipher encryption |
| **RSK-11** | QA / Context| Conversational coreference rewriting injecting spurious keywords into retrieval | 3 | 4 | 3 | **36** | High | Replace regex concatenation with lightweight local coreference parser |
| **RSK-12** | Scheduling | Lack of closed-loop renegotiation when selected model worker pool is saturated | 3 | 3 | 3 | **27** | Medium | Implement dynamic fallback renegotiation from Tier 2 back to Tier 1 |

---

## Academic Defense and Demonstration Guidelines

When demonstrating SETU-NETRA Version 1.0 to faculty review committees, examination panels, or technical auditors, adhere to the following presentation protocols:

1. **Acknowledge the 10,000 Req/Sec Boundary:** Clearly state that the $10,000\,\text{req/s}$ throughput metric is achieved exclusively by `GroundedExtractiveQAAdapter` performing in-memory dictionary lookup. Do not claim this throughput applies to neural transformer inference.
2. **Present Extractive QA Correctly:** Do not claim "zero hallucination". Present it as *bounded extractive span selection with physical canvas coordinates*, eliminating generative token confabulation while evaluating accuracy via Exact Match, Token F1, and Citation Precision.
3. **Be Candid Regarding Cloud Status:** Transparently state that cloud adapters (Gemini, Groq, OpenRouter) are fully implemented and interface-compliant, but remain classified as `NOT TESTED / NOT CONFIGURED` due to zero-credit local operation mandates.
4. **Demonstrate Fail-Safe Privacy:** Show live evidence from [`test_v1_integration.py`](file:///d:/Projects/Setu-Netra/tests/test_v1_integration.py) proving that Local-Only Privacy Mode blocks outbound network sockets with zero byte leakage.
5. **Frame Memory and Latency Properly:** Present memory consumption as *projected steady-state estimates* under controlled workloads, acknowledging that OS-level memory management can trigger paging under extreme multi-process load. Do not claim an unverified 40% P99 latency reduction; present it as an experimental hypothesis to be tested in Experiment B.
