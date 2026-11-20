# SETU-NETRA: Comprehensive Research Literature Review
## Adaptive AI Model Routing, Traffic Scheduling, & Document-Grounded Intelligence

**Report ID:** SETU-LIT-REV-002  
**Date:** November 9, 2026  
**Audience:** Academic Evaluators, CSE Minor Project Committee, System Architects  

---

## 1. Executive Summary

Modern AI systems increasingly transition from monolithic, single-model architectures toward heterogeneous multi-model ensembles. While large foundation models demonstrate extraordinary general reasoning, executing every inference request on a massive model introduces prohibitive financial cost, excessive latency, and catastrophic hardware bottlenecking.

This literature review investigates the foundational research across ten core areas spanning **model routing, inference traffic scheduling, multi-model serving, and evidence-grounded document intelligence**. It examines five seminal industry and academic systems—**FrugalGPT, RouteLLM, vLLM, Ray Serve, and LiteLLM**—analyzing their algorithms, operational boundaries, and direct lessons for the architecture of SETU-NETRA.

---

## 2. The Ten Research Domains

```
                                  +---------------------------------------+
                                  |     Incoming Multi-Modal Request      |
                                  +---------------------------------------+
                                                      |
                                                      v
                   +---------------------------------------------------------------------+
                   |                STAGE 1: MODEL SELECTION & CASCADING                 |
                   |   - Query Complexity Analysis (RouteLLM)                            |
                   |   - Task-Type Compatibility Matrix                                  |
                   |   - FrugalGPT Cascade: Lightweight SLM -> Verification -> Heavy LLM |
                   +---------------------------------------------------------------------+
                                                      |
                                      Selected Model Architecture
                                                      v
                   +---------------------------------------------------------------------+
                   |               STAGE 2: TRAFFIC MANAGEMENT & SCHEDULING              |
                   |   - Queue Scheduling (M/G/c, LOR, Shortest Estimated Time)          |
                   |   - Hardware Telemetry (CPU, GPU VRAM, Memory Bandwidth)            |
                   |   - Capacity-Aware Worker Dispatching                               |
                   +---------------------------------------------------------------------+
                                                      |
                                         Dispatched Worker Inferences
                                                      v
                   +---------------------------------------------------------------------+
                   |             STAGE 3: EVIDENCE-GROUNDED CONTEXT DELIVERY             |
                   |   - Dense Passage Retrieval (DPR) + Lexical Overlap                 |
                   |   - Strict Provenance Verification (Page, Bounding Box, Confidence) |
                   |   - Hallucination Auditing & Citation Alignment                     |
                   +---------------------------------------------------------------------+
```

---

### 2.1 LLM Routing & Query Complexity Classification
* **Core Problem:** Different prompts require vastly different reasoning capabilities. Simple extraction tasks (e.g. *"What is the date on this receipt?"*) waste compute when dispatched to a 70B parameter model, while complex analytical tasks fail on a 1B model.
* **Key Literature:**
  - *RouteLLM* (Ong et al., LMSYS / UC Berkeley, 2024): Demonstrates that lightweight classifier heads (BERT-based or matrix factorization) trained on user preference data can route $50\%\text{--}85\%$ of queries to a smaller model while preserving $95\%$ of GPT-4-level quality.
  - *Hybrid LLM Routing* (Ding et al., 2024): Evaluates embedding-based similarity against synthetic intent clusters to predict model capability boundaries.
* **Application to SETU-NETRA:** We implement a **Task and Complexity Classifier** that routes queries based on structural requirements (e.g., OCR extraction vs. formula calculation vs. open-ended synthesis).

---

### 2.2 Model Cascading & Quality-Aware Fallback
* **Core Problem:** Static routing can misclassify an ambiguous query, leading to silent failure on a small model.
* **Key Literature:**
  - *FrugalGPT* (Chen, Zaharia, & Zou, Stanford / NeurIPS 2023): Introduces LLM Cascade, where a query is sequentially queried on cheap-to-expensive models. A scoring function evaluates the completion; if confidence exceeds threshold $\tau$, execution terminates early.
  - *Self-Consistency* (Wang et al., ICLR 2023): Measures agreement across multiple sampled completions as an empirical confidence indicator.
* **Application to SETU-NETRA:** We implement **Evidence-Grounded Cascading**. A lightweight local SLM (e.g., SmolLM or Qwen2.5-0.5B/1.5B) attempts the answer. If its generated assertion lacks verifiable citations in the retrieved context blocks, the system automatically escalates to a larger model.

---

### 2.3 Mixture of Experts (MoE) vs. External Model Routing

| Dimension | Mixture of Experts (MoE) | External Model Routing (SETU-NETRA) |
| :--- | :--- | :--- |
| **Architectural Layer** | Intra-model (between Feed-Forward layers inside forward pass) | Inter-system (between separate processes, models, and workers) |
| **Routing Mechanism** | Softmax gating network over hidden vectors $\mathbf{h} \in \mathbb{R}^d$ | Multi-criteria scheduler over request metadata & hardware telemetry |
| **Coupling** | Tightly coupled; all experts must share weight formats and GPU memory | Fully decoupled; combines OCR, embeddings, SLMs, and external LLMs |
| **Failure Isolation** | Single-point failure; CUDA OOM halts the entire model | Robust fault-isolation; failed worker routes to alternative replica |
| **Literature** | Shazeer et al. (*ICLR 2017*); Switch Transformers (*JMLR 2022*) | FrugalGPT (*NeurIPS 2023*); RouteLLM (*LMSYS 2024*) |

---

### 2.4 Inference Load Balancing & Queue Scheduling
* **Core Problem:** High concurrency leads to head-of-line blocking if long-running generation jobs stall fast retrieval requests.
* **Key Literature:**
  - *The Power of Two Choices in Randomized Load Balancing* (Mitzenmacher, IEEE TPDS 2001): Proves that selecting the worker with the shortest queue between two randomly chosen candidates dramatically reduces tail latency compared to naive round-robin.
  - *Least Outstanding Requests (LOR)*: Balances inflight requests across heterogeneous workers.
  - *Shortest Processing Time First (SPT / SECT)*: Minimizes average waiting time under varying prompt lengths.
* **Application to SETU-NETRA:** We implement and benchmark 6 explicit algorithms: **Round Robin, Random, Least Outstanding Requests (LOR), Shortest Estimated Completion Time (SECT), Capacity-Aware (telemetry-weighted), and Adaptive Reinforcement/Heuristic Routing**.

---

### 2.5 Multi-Model Serving & Dynamic Batching
* **Core Problem:** Loading multiple neural models into constrained RAM/VRAM causes out-of-memory crashes or severe disk paging.
* **Key Literature:**
  - *vLLM / PagedAttention* (Kwon et al., SOSP 2023): Eliminates KV-cache fragmentation by paging memory across non-contiguous blocks.
  - *Orca* (Yu et al., OSDI 2022): Iteration-level scheduling enabling continuous batching of variable-length prompts.
* **Application to SETU-NETRA:** Given our single-laptop development environment (16 GB RAM, CPU-only PyTorch), models must be lazily loaded, cached with LRU policies, and executed sequentially or with strict worker concurrency caps to avoid swapping.

---

### 2.6 Cost-Quality Optimization
* **Core Problem:** Achieving Pareto-optimal trade-offs between monetary expenditure ($/token), computational latency (ms), and factual accuracy.
* **Key Literature:**
  - *Cost-Effective LLM Serving* (Patel et al., ASPLOS 2024): Optimizing resource allocation for heterogeneous multi-tenant LLM workloads.
  - *Pareto-Optimal Routing* (Mohammadi et al., 2024): Formulating model selection as an integer linear program (ILP) balancing budget and performance.

---

### 2.7 Document-Grounded RAG & Evidence Verification
* **Core Problem:** Generative LLMs hallucinate answers that appear plausible but contradict source text.
* **Key Literature:**
  - *Dense Passage Retrieval (DPR)* (Karpukhin et al., EMNLP 2020): Dual-encoder dense vector matching.
  - *Self-RAG: Learning to Retrieve, Generate, and Critique* (Asai et al., ICLR 2024): Interleaves generation with critique tokens (`[IsRel]`, `[IsSup]`, `[IsUse]`) to audit whether generation is supported by retrieved context.
  - *Corrective RAG (CRAG)* (Yan et al., 2024): Evaluates retrieval confidence and triggers web search or knowledge fallback if retrieval is weak.
* **Application to SETU-NETRA:** Every generated assertion must contain a verifiable citation tag (`[Doc: <name>, Page: <p>, Block: <b>]`) directly matching bounding boxes stored in SQLite.

---

## 3. Deep-Dive Investigation of Five Flagship Projects

```
+--------------------------------------------------------------------------------------------------------+
|                                    COMPARATIVE SYSTEM LANDSCAPE                                        |
+-------------------+---------------------------+---------------------------+----------------------------+
| System            | Primary Focus             | Core Algorithm            | Key Limitation             |
+-------------------+---------------------------+---------------------------+----------------------------+
| 1. FrugalGPT      | API Cost Minimization     | Cascade Thresholding      | Requires labeled training  |
| 2. RouteLLM       | Binary Preference Routing | Matrix Factorization Head | Ignores hardware telemetry |
| 3. vLLM           | High-Throughput Serving   | PagedAttention & Iteration| Requires GPU cluster       |
| 4. Ray Serve      | Distributed Pipeline DAG  | Actor Placement & HTTP    | Heavy cluster footprint    |
| 5. LiteLLM        | API Schema Unification    | Format Translation Proxy  | No intelligent scheduling  |
+-------------------+---------------------------+---------------------------+----------------------------+
| SETU-NETRA        | Document Intelligence &   | Evidence-Grounded         | Designed for lightweight   |
|                   | Capacity-Aware Routing    | Telemetry Scheduling      | & local hardware execution |
+-------------------+---------------------------+---------------------------+----------------------------+
```

### 3.1 FrugalGPT (Stanford University, 2023)
* **Problem Solved:** Massive cost inflation when querying proprietary APIs (GPT-4) for queries that cheaper models (GPT-3.5, Claude Instant) could easily resolve.
* **Algorithm:** Combines three strategies:
  1. *Prompt Adaptation:* Compressing prompts to minimize input tokens.
  2. *LLM Approximation:* Using specialized local models for fixed tasks.
  3. *LLM Cascade:* Sequential execution through a chain of models $[M_1, M_2, \dots, M_K]$. A trained regression scorer evaluates completion $y_1$ from $M_1$. If $f(y_1) \ge \tau_1$, return $y_1$; otherwise query $M_2$.
* **Limitations:** Focuses exclusively on external commercial API prices ($/token). Assumes infinite worker capacity and zero queue wait times. Does not account for local memory saturation, model loading latencies, or physical CPU/GPU contention.
* **Relevance to SETU-NETRA:** Provides the theoretical framework for cascading, but SETU-NETRA replaces black-box quality scoring with **evidence-grounded fact checking against OCR bounding boxes**.

---

### 3.2 RouteLLM (LMSYS Organization, 2024)
* **Problem Solved:** Binary routing between an expensive model (GPT-4) and a cheap model (Mixtral 8x7B / Llama-3-8B).
* **Algorithm:** Evaluates four router variants:
  1. *Random & Constant Router* (Baselines).
  2. *Matrix Factorization Router:* Learns vector embeddings for prompt tokens and model preferences.
  3. *BERT Classifier Router:* Fine-tunes a DeBERTa head on pairwise win-loss preference annotations.
  4. *Causal LLM Router:* Uses an instruction-tuned 7B model to evaluate prompt hardness.
* **Limitations:** Requires tens of thousands of preference pairs (Chatbot Arena dataset). Assumes routing is purely a function of text complexity, completely ignoring physical worker health, GPU availability, and inflight request queues.
* **Relevance to SETU-NETRA:** We adopt lightweight query feature extraction (token length, domain specificity, structural requirements) for model selection, while explicitly coupling it to downstream worker scheduling.

---

### 3.3 vLLM (UC Berkeley, 2023)
* **Problem Solved:** Traditional LLM serving allocates contiguous memory for the maximum possible sequence length for every request, wasting $60\%\text{--}80\%$ of GPU VRAM due to internal/external fragmentation.
* **Algorithm:** *PagedAttention* divides KV-caches into fixed-size virtual blocks (pages) stored in non-contiguous physical memory, akin to operating system virtual memory.
* **Limitations:** Requires CUDA-capable NVIDIA GPUs and compiled C++/CUDA kernels. Highly optimized for batch throughput of a *single* loaded model; does not address routing across heterogeneous model types (OCR + Embeddings + SLMs).
* **Relevance to SETU-NETRA:** Benchmarking standard for continuous batching and token generation throughput.

---

### 3.4 Ray Serve (Anyscale / UC Berkeley, 2020)
* **Problem Solved:** Serving multi-stage machine learning pipelines (e.g. Ingestion $\to$ Embedding $\to$ Retrieval $\to$ Generation) across a distributed cluster with auto-scaling.
* **Algorithm:** Python actor-based distributed deployment. Workers are stateful Python classes orchestrated by an HTTP proxy controller that monitors queue depth and scales replicas.
* **Limitations:** Extremely heavy footprint. Running Ray requires a cluster coordinator, Global Control Store (Redis/GCS), and shared-memory Plasma stores, consuming gigabytes of RAM before processing a single request.
* **Relevance to SETU-NETRA:** Inspires our decoupled worker pool architecture, but SETU-NETRA implements a lightweight, native Python multi-threaded/multi-process worker engine with zero external distributed dependencies.

---

### 3.5 LiteLLM (BerriAI, 2023–2024)
* **Problem Solved:** Fragmentation of client SDKs across dozens of commercial and open-source model providers (OpenAI, Anthropic, Bedrock, Ollama, HuggingFace).
* **Algorithm:** Translates heterogeneous REST payloads into OpenAI-compatible JSON formats with basic static fallbacks (e.g., if model A fails, call model B).
* **Limitations:** Purely a syntactic gateway. Performs zero intelligent scheduling, zero queue prioritization, zero hardware telemetry monitoring, and zero content verification.
* **Relevance to SETU-NETRA:** We adopt a clean unified inference interface (`UnifiedModelInterface`), but provide the missing intelligence: capability modeling, telemetry-driven worker dispatching, and evidence verification.

---

## 4. Defensible Engineering & Research Contribution of SETU-NETRA

We do not claim novelty merely by integrating existing libraries. SETU-NETRA's defensible scientific contribution lies at the **intersection of document grounding and capacity-aware model routing**:

> **Core Research Thesis:**  
> *"Existing LLM routers (RouteLLM, FrugalGPT) route prompts in isolation based purely on textual query complexity, while inference schedulers (vLLM, Ray Serve) schedule requests based purely on hardware queue depths.  
> By integrating **document provenance confidence (OCR quality, retrieval similarity) with local hardware telemetry (worker queue depth, RAM pressure)** into a unified, capacity-aware routing and cascading policy, SETU-NETRA can achieve higher answer factual grounding while cutting average tail latency and preventing resource starvation on constrained hardware."*
