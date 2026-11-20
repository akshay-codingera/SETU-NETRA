# SETU-NETRA Version 1.0 — Known Limitations & System Boundaries

## Executive Summary

SETU-NETRA Version 1.0 is an intelligent document understanding, evidence-grounded question-answering, and adaptive model orchestration platform engineered to operate reliably on standard consumer and workstation hardware without external cloud dependencies. 

To maintain scientific integrity and engineering transparency, this document details the verified operational boundaries, physical hardware constraints, algorithmic assumptions, and known limitations of the Version 1.0 implementation.

---

## 1. System Capabilities: What SETU-NETRA Can and Cannot Do

### What SETU-NETRA Version 1.0 CAN Do:
1. **Multi-Format Ingestion**: Ingest and paginate PDF, DOCX, TXT, and scanned image files into an evidence-preserving SQLite repository with deterministic document IDs.
2. **Deterministic Layout Reconstruction**: Detect whitespace gutters and split multi-column reading regions using Recursive XY-Cut while preserving spatial bounding boxes.
3. **Dense & Lexical Hybrid Search**: Retrieve document passages using 384-dimensional sentence transformer embeddings (MiniLM) combined with lexical matching, applying non-negative cosine score rectification (ReLU clipping) and duplicate suppression.
4. **Evidence-Grounded Answering**: Generate answers strictly tied to cited document passages and assign epistemically audited status (`EVIDENCE_BACKED`, `UNSUPPORTED`, `GENERAL_KNOWLEDGE`).
5. **Adaptive Model Routing**: Route incoming questions dynamically between lightweight extractive engines and generative Small Language Models (SLMs) based on question complexity, evidence requirements, and privacy settings.
6. **Capacity-Aware Traffic Scheduling**: Manage multi-worker inference queues using six scheduling strategies (Round Robin, Random, Least Outstanding, SECT, CAS, ARS) with EWMA latency estimation and circuit breakers.
7. **Multi-Turn Persistent Sessions**: Maintain conversation histories in SQLite, resolve deictic pronouns (*"What does it cache?"*) against prior exchanges, and persist turn-by-turn provenance.
8. **Strict Local-Only Privacy**: Guarantee that zero document bytes or query texts leave the local machine when Local-Only Privacy Mode is active.

### What SETU-NETRA Version 1.0 CANNOT Do:
1. **Unconstrained Web Browsing**: SETU-NETRA does not scrape the live internet or retrieve external web citations; its knowledge is strictly grounded in user-provided documents.
2. **Handwritten Script Decipherment**: The bundled EasyOCR (CRAFT + CRNN) model is trained for printed digital typography and performs poorly on unconstrained cursive or handwriting.
3. **Arbitrary Image Understanding**: Non-text visual components (e.g., complex biological schematics, photographic diagrams, or medical scans) are not interpreted semantically unless accompanied by OCR-readable text captions.
4. **Infinite Context Synthesis**: Local SLMs cannot accept 100,000+ token contexts on CPU without paging thrashing. Context is deliberately bounded to top-$K$ passages ($K \le 5$).
5. **Multi-Master Distributed Clustering**: The Version 1.0 persistence layer is anchored in SQLite, which supports single-writer concurrency and is bounded to a single host.

---

## 2. Hardware Requirements & Host Constraints

SETU-NETRA Version 1.0 was evaluated on the baseline host configuration:
- **CPU**: Intel Core i5-1334U (10 cores, 12 threads: 2 Performance cores, 8 Efficient cores, up to 4.60 GHz).
- **RAM**: 16 GB DDR4/DDR5.
- **Storage**: Fast NVMe SSD ($\ge 10\,\text{GB}$ free space).
- **Operating System**: Windows 11 / Linux (Ubuntu 22.04+) / macOS (Apple Silicon).

### Physical Bottlenecks & Operational Constraints:

| Hardware Resource | Minimum Required | Recommended | Observed Constraint / Failure Mode |
| :--- | :--- | :--- | :--- |
| **System RAM** | 8 GB | 16 GB | If available memory drops below $2.0\,\text{GB}$, PyTorch CPU allocation or Ollama background workers may trigger OS memory compression or swap thrashing. |
| **CPU Inference** | 4 Cores (x86_64 or ARM64) | 8+ Cores | Autoregressive generative token generation on CPU runs at $8\text{--}18\,\text{tokens/sec}$. High concurrency ($> 4$ parallel generative requests) induces CPU contention and increases queue backlog. |
| **Disk I/O** | 5 GB SSD | 20 GB NVMe | SQLite WAL mode requires sequential write speeds. Mechanically spinning HDDs will experience latency spikes during bulk embedding matrix reads. |

---

## 3. Model-Specific Limitations & Context Lengths

| Model Identifier | Provider / Engine | Context Window | Throughput (Tokens/s) | Known Operational Limitations |
| :--- | :--- | :---: | :---: | :--- |
| `grounded-extractive-qa-v1` | SETU-NETRA Native | $2,048$ chars | $> 5,000\,\text{req/s}$ | **Lexical/Span extraction only**. Cannot synthesize novel reasoning, compute multi-document mathematical averages, or rephrase content. |
| `smollm2-135m-instruct` | HuggingFaceTB / Transformers | $2,048$ tokens | $\sim 15\,\text{tok/s}$ (CPU) | **Small parameter scale (135M)**. Capable of concise summaries and comparative answers, but exhibits degraded coherence on multi-step propositional logic. |
| `neural_all-MiniLM-L6-v2` | Sentence-Transformers | $256$ tokens | $\sim 300\,\text{texts/s}$ | Sentences exceeding 256 WordPiece tokens are truncated. Long document paragraphs must be split into chunks $\le 100$ words. |
| `easyocr-craft-crnn` | JaidedAI | Full Page Image | $0.2\text{--}0.5\,\text{pages/s}$ | Single-threaded CPU vision pipeline is computationally heavy ($1.5\text{--}4.0\,\text{s}$ per page). PDF rasterization requires PyMuPDF. |
| `ollama/qwen2.5:1.5b` | Ollama Local Daemon | $8,192$ tokens | $\sim 18\text{--}25\,\text{tok/s}$ | Requires external Ollama daemon running on `localhost:11434`. If daemon is killed or uninstalled, adapter marks itself `UNAVAILABLE`. |
| `google/gemini-2.0-flash` | Google Cloud API | $32,768$ tokens | $\sim 30\text{--}50\,\text{tok/s}$ | Requires outbound internet and API key. Strictly blocked when Local-Only Privacy Mode is toggled ON. |
| `groq/llama-3.1-8b-instant` | Groq Cloud LPUs | $8,192$ tokens | $\sim 150\,\text{tok/s}$ | Requires Groq API key. Subject to remote rate limits (RPM/TPM). Blocked in Local-Only mode. |

---

## 4. OCR & Vision Pipeline Boundaries

1. **Language Scope**: The bundled default EasyOCR recognition model is configured for English (`['en']`). Ingestion of multilingual documents in non-Latin scripts (e.g., Devanagari, Arabic, CJK) requires additional language pack configuration in the OCR adapter.
2. **Complex Embedded Tables**: While `docx_loader` parses native XML table structures with full cell boundaries, OCR-based table extraction from scanned PDF images relies on bounding-box proximity. Merged cells or borderless accounting tables may suffer minor token-order interleaving.
3. **Low-Resolution Artifacts**: Scans below $150\,\text{DPI}$ or with severe perspective skew exhibit degraded CRNN character confidence ($< 0.60$). The pipeline flags low-confidence blocks, but cannot hallucinate unreadable characters.

---

## 5. Concurrency Limits & Scheduling Boundaries

1. **CPU-Bound Inference Saturation**:
   Unlike GPU clusters with large tensor-parallel memory bandwidth, CPU execution is fundamentally compute-bound. In Stage 6 stress testing, saturated worker pools under 100 concurrent requests exhibited queue queuing latency ($Q_w$). To protect system stability:
   - Worker queues are capped at `max_queue_size = 50`.
   - Backpressure triggers `HTTP 429 / 503` rejection when queues are saturated.
2. **Single-Threaded Python GIL**:
   While `InferenceWorkerPool` uses Python worker threads and `SimpleHTTPRequestHandler` utilizes `ThreadingHTTPServer`, CPU-bound model adapters (PyTorch C++ backend) release the GIL during matrix math, but Python pre-processing retains the GIL. Optimal CPU concurrency is achieved with $W = 4\text{--}8$ active workers.

---

## 6. Scalability Boundaries & Storage Architecture

1. **SQLite Database Locking**:
   Version 1.0 persists documents, blocks, embeddings, conversations, and messages in a single SQLite database (`setu_netra.db`) with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`).
   - SQLite allows unlimited concurrent readers, but serializes writers with a single writer lock.
   - For workloads with thousands of simultaneous document uploads per minute, the database writer lock will become a throughput bottleneck.
2. **In-Memory Embedding Stacking**:
   `DocumentRetriever` retrieves all embeddings matching the target engine and stacks them into an $(N, D)$ NumPy array for vectorized cosine computation.
   - For up to $50,000$ document blocks ($50,000 \times 384 \times 4\,\text{bytes} \approx 76.8\,\text{MB}$), matrix multiplication takes $< 5\,\text{ms}$ on CPU.
   - For enterprise repositories exceeding $500,000$ passages, an approximate nearest neighbor (ANN) vector index (e.g., HNSW or FAISS) will be required.

---

## 7. Recommendations for Future Milestones

1. **Vector Index Acceleration**: Integrate an embedded HNSW vector index (e.g., `usearch` or `faiss-cpu`) to scale dense passage retrieval beyond $100,000$ blocks with sub-millisecond lookup.
2. **Asynchronous Background OCR**: Decouple document upload from OCR extraction via a persistent background job queue, allowing multi-hundred-page PDFs to process asynchronously without blocking HTTP client threads.
3. **Quantized GGUF Native Execution**: Package `llama.cpp` Python bindings (e.g., `llama-cpp-python`) directly within the environment to provide native 4-bit quantized SLM inference with zero external daemon dependencies.
4. **PostgreSQL / Distributed Storage Option**: For multi-tenant or clustered deployments, provide an optional PostgreSQL / pgvector backend while preserving SQLite as the default zero-config local engine.
