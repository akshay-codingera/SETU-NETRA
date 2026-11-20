# SETU-NETRA V1.1 Experimental Limitations & Boundary Conditions
## Critical Assessment of Hardware Constraints, Model Boundaries, and Threats to Validity

> **Document ID:** SETU-NETRA-V1.1-EXP-LIMIT-001  
> **Target Version:** V1.1 Baseline Infrastructure  
> **Status:** APPROVED & ARCHIVED  
> **Date:** November 10, 2026  
> **Author:** Senior AI Systems Benchmarking Engineer & Experimental Researcher  
> **Related Protocol:** [`reports/V1_1_BASELINE_PROTOCOL.md`](file:///d:/Projects/Setu-Netra/reports/V1_1_BASELINE_PROTOCOL.md)  
> **Related Results:** [`reports/V1_1_BASELINE_RESULTS.md`](file:///d:/Projects/Setu-Netra/reports/V1_1_BASELINE_RESULTS.md)  

---

## 1. Introduction and Scope of Critical Appraisal

Scientific rigor requires transparent documentation of experimental constraints, methodological assumptions, hardware bottlenecks, and potential threats to internal and external validity. This report identifies the boundary conditions governing the SETU-NETRA V1.1 baseline findings, clarifying what the empirical results prove and where extrapolation must be strictly avoided.

---

## 2. Consumer Hardware Constraints & Concurrency Bottlenecks

### 2.1 CPU-Bound Autoregressive Generation
* **Physical Constraint:** The host system operates on an Intel 10-core consumer processor with 16 GB physical RAM and no discrete GPU acceleration. The inference pipeline relies on the PyTorch CPU backend (`torch.float32`).
* **Thread Contention:** Generative inference for `smollm2-135m-instruct` utilizes multiple OpenMP/MKL CPU threads per token generation. When multiple client threads simultaneously submit generative requests:
  1. CPU core saturation immediately reaches 100%.
  2. Single-request execution time degrades from $\sim 800\,\text{ms}$ (sequential) to $>30,000\,\text{ms}$ (under 4 concurrent threads).
* **Circuit-Breaker Tripping:** As observed during early high-concurrency stress testing, when queue wait plus execution time exceeds the worker's $30.0\,\text{s}$ timeout guard, the worker's resilient circuit breaker triggers, entering a 5-second `COOLING_DOWN` state. This demonstrates that **running multiple concurrent autoregressive SLMs on unaccelerated consumer CPUs is physically unsustainable without model routing or quantized backends**.

### 2.2 Memory Footprint and Operating System Swapping
* The host environment has $\sim 5,000\,\text{MB}$ of available RAM at rest.
* Running `all-MiniLM-L6-v2` ($\sim 400\,\text{MB}$) concurrently with `SmolLM2-135M` ($\sim 600\,\text{MB}$ in FP32) and SQLite in WAL mode leaves limited headroom for larger multi-billion parameter models (e.g. 7B or 13B models).
* Attempting to load models larger than 1.5B parameters on this hardware risks OS memory swapping, page-thrashing, and non-deterministic latency spikes.

---

## 3. Small Language Model (SLM) Architectural Boundaries

### 3.1 Context Overload and Prompt Repetition in 135M Parameter Models
* **Prompt Length Sensitivity:** The standard synthesized context prompt packages retrieved evidence blocks, system instructions, and citation formats, totaling $300\text{--}450$ tokens.
* **Empirical Failure Mode:** At 134.5 million parameters, `smollm2-135m-instruct` lacks the semantic capacity to reliably process long multi-passage contexts and generate constrained answers within small generation budgets (45 tokens). In several sequential evaluations, SmolLM2 echoed the prompt delimiters (e.g., `User Query:\n... EVIDENCE BLOCK 1:\n...`) rather than isolating the direct factual answer.
* **Citation Syntax Non-Compliance:** SmolLM2 consistently failed to emit structured citation tags in the requested format `[Doc: <name>, Page: <p>, Block: <b>]`, yielding a Citation Precision of only **$0.1000$** (attributable solely to the 10 unsupported queries which correctly have no citations). In contrast, the specialized `grounded-extractive-qa-v1` adapter achieved **$0.8200$** citation precision.

### 3.2 Exact Match (EM) Metric Infeasibility
* In all four experimental conditions, **Exact Match was $0.0000$**.
* **Root Cause:** The ground-truth reference answers in `qa_evaluation_queries.json` are concise grammatical noun phrases (e.g. *"programmer's logical address space from physical DRAM memory"*). In contrast:
  * Extractive QA outputs complete verified sentences with provenance citations (e.g. *"Virtual memory decouples the programmer's logical address space from physical DRAM memory. [Doc: doc_operating_systems.txt, Page: 1, Block: 2]"*).
  * Generative QA outputs full explanatory paragraphs.
* **Methodological Conclusion:** Exact Match is an invalid metric for evaluating evidence-grounded document QA systems that emit structured provenance citations. **Token F1 and Passage Citation Precision must serve as the primary ground-truth metrics**.

---

## 4. Benchmark Corpus & Query Dataset Scope

### 4.1 Domain Homogeneity
* The evaluation corpus consists of 3 high-density technical documents covering Computer Systems (Operating Systems, Raft Consensus, Database Concurrency).
* **Limitation:** While technical documents provide rigorous tests for algorithmic terminology, hierarchical structures, and precise definitions, they do not test:
  * Scanned noisy OCR documents with heavy degradation.
  * Complex multi-column financial tables or balance sheets.
  * Multi-lingual or non-English scripts.
  * Legal contracts with complex multi-clause dependencies.

### 4.2 Query Dataset Size ($N = 100$)
* Although $N = 100$ provides $>85\%$ statistical power for repeated-measures ANOVA on the same items, it remains a moderate sample size compared to web-scale IR benchmarks (e.g. MS-MARCO with 500,000 queries).
* Generalizability to long-tail conversational user interactions must be validated in future milestones with larger and more diverse query distributions.

---

## 5. Synthetic vs. Live Load Benchmark Disentanglement

To ensure scientific honesty, the distinction between the Synthetic Scheduler Load test and the End-to-End Live Load test must be strictly maintained:

| Attribute | Synthetic Load Benchmark ($N = 1,000$) | Live Concurrent E2E Benchmark ($N = 20$) |
| :--- | :--- | :--- |
| **Execution Engine** | `CalibratedMockAdapter` with empirical delays (SLM: $\mu=120\text{ms}$, Extractive: $\mu=1.5\text{ms}$) | Real `DocumentIntelligencePipeline` + `BenchmarkQAEngine` + live SQLite store |
| **Workload Scale** | 1,000 requests per condition (4,000 total) | 20 requests per condition (80 total) |
| **Primary Metric** | Queuing dynamics, tail percentiles ($P_{99}$ with 95% CIs), goodput, SLO violations | End-to-end CPU contention, live SQLite retrieval time, actual model execution latency |
| **Limitation** | Mock execution does not consume CPU cycles, isolating scheduler queue math from hardware thread thrashing | Small request count ($N = 20$) due to CPU exhaustion when running concurrent unquantized PyTorch models |

Neither benchmark should be presented as replacing the other: the synthetic test rigorously validates the mathematical queue theory of the scheduling algorithms at scale ($N \ge 1,000$), while the live test captures actual host hardware friction under multi-threading.

---

## 6. Threats to Validity

### 6.1 Internal Validity
* **Process Thread Contention:** Background OS tasks and Python Global Interpreter Lock (GIL) contention can introduce minor latency jitter. We mitigated this by setting fixed random seeds (`seed=42`) and reporting bootstrapped 95% confidence intervals across 1,000 resamples.
* **SQLite Concurrency:** SQLite in WAL mode allows concurrent readers but serializes writers. In read-heavy QA evaluation, SQLite contention is negligible ($<2\,\text{ms}$ query time), but under heavy parallel indexing, database locking would become a bottleneck.

### 6.2 External Validity
* **Model Specificity:** Findings comparing `smollm2-135m-instruct` to `grounded-extractive-qa-v1` cannot be blindly extrapolated to 70B parameter frontier models (e.g. GPT-4o, Gemini 1.5 Pro), where generative citation precision is significantly higher.
* **Task Type Distribution:** The synthetic load test assumed a 70% factual / 30% synthesis workload split. If a deployment workload consists of 95% multi-page creative summarization, the latency advantages of adaptive routing will naturally diminish as requests route predominantly to generative workers.

---

## 7. Concrete Roadmap Requirements for Version 1.1

To address the limitations exposed by this baseline evaluation, the following architectural upgrades are recommended for V1.1 implementation:

1. **Quantized Execution Backend (GGUF / ONNX Runtime):**
   * Replace raw FP32 PyTorch CPU execution for SLMs with 4-bit / 8-bit quantized backends (e.g. `llama-cpp-python` or ONNX Runtime with INT8 quantization). This will reduce memory usage by 75% and accelerate CPU token generation by $3\text{--}5\times$.
2. **Grammar-Guided Constrained Decoding:**
   * Enforce citation syntax and structured JSON output at the decoder level (e.g. via Outlines or JSON schema logit masking) to prevent SLM prompt echoing and citation omissions.
3. **Dynamic Context Budgeting:**
   * Adaptively compress retrieved context passages based on query intent rather than passing a static 1,500-token window, preventing prompt overload in small models.
4. **Expanded Multi-Domain Benchmark Corpus:**
   * Incorporate public benchmarks (e.g. DocVQA, FinanceBench) to test diverse document formats, tables, and noisy OCR layouts.
