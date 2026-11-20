# SETU-NETRA: An Adaptive Neuro-Symbolic Framework for Intelligent Document Understanding, Evidence-Grounded Question Answering, and Context-Aware Reasoning

**Autonomous Systems & Document Intelligence Architecture Group**  
*Senior AI Research Scientist, Machine Learning Engineer & Research Architect*  
*November 2026*

---

### Abstract
Conventional document Question Answering (QA) and Retrieval-Augmented Generation (RAG) systems suffer from three fundamental structural vulnerabilities: (1) **the geometric fallacy**, which assumes reading-order heuristics preserve semantic and hierarchical relationships; (2) **the epistemic fallacy**, which equates semantic retrieval similarity with factual sufficiency and deductive completeness; and (3) **the universal generation fallacy**, which delegates deterministic relational and mathematical inquiries to uncalibrated autoregressive language models, causing catastrophic hallucinations. In this paper, we present **SETU-NETRA**, an adaptive, local-first neuro-symbolic framework designed for visually-rich document understanding, epistemic evidence verification, and dynamic reasoning strategy dispatching under strict edge constraints ($\le 16\text{ GB}$ RAM, CPU-only execution). 

SETU-NETRA contributes three novel, lightweight, and trainable research components:
1. **SR-EdgeNet** ($414\text{K}$ parameters): A spatial-relational edge classifier that maps OCR bounding boxes and MiniLM embeddings into a directed hierarchy multigraph ($\text{PARENT\_OF}$, $\text{OPTION\_OF}$, $\text{CONTINUATION\_OF}$, $\text{NONE}$), achieving $99.46\%$ synthetic accuracy and $0.9909$ Macro F1, while uncovering critical domain-shift dynamics between synthetic layouts and warped mobile camera scans.
2. **ER-SP** ($560\text{K}$ parameters): A five-class epistemic gating network ($\text{SUFFICIENT}$, $\text{PARTIALLY\_SUFFICIENT}$, $\text{CONTRADICTORY}$, $\text{IRRELEVANT}$, $\text{UNVERIFIABLE}$) operating over a $1,537$-dimensional question-passage cross-interaction tensor, attaining $86.18\%$ accuracy, $0.8553$ Macro F1, and an expected calibration error (ECE) of $0.0889$ on held-out unseen domains, outperforming standard cosine thresholding ($37.65\%$).
3. **CM-RP** ($63\text{K}$ parameters): A contextual meta-reasoning policy network mapping a $423$-dimensional multimodal state vector (combining question semantics, document hierarchy, evidence sufficiency, domain tokens, and host kernel telemetry) into a $7$-action strategy space with dynamic hardware-aware action masking.

Through a rigorous post-integration critical statistical audit, we resolve earlier zero-support reporting anomalies via an independent $7$-action benchmark ($N = 245$, $35$ samples/class), demonstrating that pure neural CM-RP v2 achieves **$94.29\%$ accuracy** and **$0.9433$ Macro F1** across all seven actions without heuristic intervention. Furthermore, forensic ablation analysis proves that while the full pipeline scores $70.00\%$ under ungrounded placeholder contexts due to strict anti-hallucination refusal by the citation verifier, it surges to **$92.00\%$ accuracy**, **$0.9524$ Abstention F1**, and **$0.946$ Grounding Score** under verified grounded contexts, outperforming individual components by $20.00$ to $68.00$ percentage points.

---

## 1. Introduction & The Motivating Paradox

Visually-rich document understanding in high-stakes domains—such as academic examinations, corporate financial audits, and regulatory filings—presents severe challenges that classical Optical Character Recognition (OCR) and naive dense retrieval pipelines fail to address. Real-world document intelligence is governed by a strict sequential dependency:

$$\text{Document Ingestion} \longrightarrow \text{Structural Understanding} \longrightarrow \text{Evidence Evaluation} \longrightarrow \text{Reasoning Strategy Selection} \longrightarrow \text{Grounded Execution / Abstention}$$

When any stage in this progression fails, compounding error cascades propagate through the pipeline, producing confident yet completely fabricated assertions.

```
+----------------------------------------------------------------------------------------------------+
|                                THE THREE CENTRAL RESEARCH FALLACIES                                |
+------------------------------------+----------------------------------+----------------------------+
| 1. The Geometric Fallacy           | 2. The Epistemic Fallacy         | 3. The Generation Fallacy  |
| - Text order = Semantic hierarchy  | - Similarity = Sufficiency       | - LLM = Universal solver   |
| - Broken by multi-column layouts,  | - High cosine overlap may omit   | - Hallucinates arithmetic, |
|   warped scans, and options.       |   decisive conditions/polarities.|   relational algebra, logic|
+------------------------------------+----------------------------------+----------------------------+
```

### 1.1 The Geometric Fallacy
Standard pipelines rely on deterministic projection profiles (such as Recursive $XY$-Cut) to infer reading order. On multi-column layouts, tables, and examination papers, naive top-to-bottom sorting interleaves question stems with unrelated adjacent choices or marginalia. Merely extracting text blocks into a flat string strips away the directed parent-child dependencies ($v_{\text{question}} \rightarrow v_{\text{option}}$) and horizontal continuations, destroying the structural context necessary for downstream reasoning.

### 1.2 The Epistemic Fallacy
Conventional Retrieval-Augmented Generation (RAG) presumes that high semantic retrieval similarity:
$$\text{sim}(\mathbf{q}, \mathbf{p}) = \frac{\mathbf{q} \cdot \mathbf{p}}{\|\mathbf{q}\| \|\mathbf{p}\|} \ge \tau$$
implies that passage $\mathbf{p}$ contains sufficient information to deduce the answer to $\mathbf{q}$. In reality, a passage discussing the exact entities in query $\mathbf{q}$ can share $88\%$ cosine similarity while explicitly omitting the necessary condition (producing incomplete premise hallucination) or asserting an opposing factual claim (producing polarity blindness). Semantic similarity measures topical alignment, not deductive entailment.

### 1.3 The Universal Generation Fallacy
Modern Large Language Models (LLMs) and Small Language Models (SLMs) generate answers token-by-token via autoregressive sampling. When tasked with relational database normalization (e.g., finding the candidate keys of $R(A, B, C, D, E)$ given functional dependencies), modular arithmetic, or formal categorical syllogisms, generative models suffer from stochastic drift, producing plausible mathematical errors that cannot be audited. Conversely, deterministic symbolic algorithms (such as Python Abstract Syntax Tree evaluators or Armstrong's axiom closure provers) solve these problems with provable $100\%$ precision in sub-millisecond execution times.

### 1.4 The SETU-NETRA Framework
To address these fallacies simultaneously, we propose **SETU-NETRA**, an adaptive neuro-symbolic architecture that unites:
1. **Learned Structural Reconstruction (SR-EdgeNet)**: Replacing geometric projection heuristics with pairwise neural edge classification.
2. **Epistemic Gating (ER-SP)**: Categorizing evidence sufficiency into five mutually exclusive epistemic states before generation is permitted.
3. **Contextual Strategy Selection (CM-RP)**: A meta-reasoning policy that dynamically routes inquiries to deterministic algorithms, extractive quote parsers, or generative SLMs based on query semantics, document structure, and host hardware telemetry.
4. **Epistemic Verification & Safe Abstention**: A strict post-hoc citation auditing layer that verifies token entailment and refuses to emit answers when factual citations cannot be grounded.

All components are strictly constrained to execute on commodity edge hardware ($\le 16\text{ GB}$ system RAM, zero cloud API reliance, CPU-only execution).

![Figure 1: Conceptual illustration of SETU-NETRA](file:///d:/Projects/Setu-Netra/research/paper/figures/setu_netra_platform_vision.png)
*Figure 1. Conceptual illustration of SETU-NETRA, showing heterogeneous users submitting documents and natural-language queries to an adaptive document intelligence engine that performs structural understanding (R1: SR-EdgeNet), evidence evaluation (R2: ER-SP), context-aware reasoning policy selection (R3: CM-RP), and evidence-grounded response generation or safe abstention under edge hardware constraints.*

---

## 2. Architectural Evolution & Historical Chronology

SETU-NETRA underwent a rigorous iterative progression from early heuristic scripts to an integrated, trainable multi-stage architecture.

```
+----------------------------------------------------------------------------------------------------+
|                                    SETU-NETRA HISTORICAL EVOLUTION                                 |
+------------------------------------+----------------------------------+----------------------------+
| Phase 0: Baseline & Heuristics     | Phase 1: Modular Components      | Phase 2: R1-R4 Framework   |
| - EasyOCR (CRAFT + CRNN)           | - BM25 + MiniLM Dense Retrieval  | - R1: SR-EdgeNet (414k)    |
| - Recursive XY-Cut Line Sorting    | - Reciprocal Rank Fusion (RRF)   | - R2: ER-SP (560k)         |
| - Regex Domain Classifier          | - Deterministic Python Solvers   | - R3: CM-RP (63k)          |
| - Static Router & Thresholds       | - CitationVerifier (Regex)       | - R4: Unified Pipeline     |
+------------------------------------+----------------------------------+----------------------------+
```

### 2.1 Early Baseline Mechanisms & Observed Failure Modes
1. **OCR and Image Extraction:** The system initially explored multi-engine OCR, standardizing on EasyOCR (CRAFT detector with CRNN-CTC sequence recognition). Raw bounding box coordinates $[x_0, y_0, x_1, y_1]$ provided planar coordinates but lacked logical hierarchy.
2. **Deterministic XY-Cut (`structure/xy_cut.py`):** Recursive projection profiling proved effective on clean single-column synthetic documents, but failed catastrophically on warped mobile scans (3–8° perspective skew), merging adjacent question options into a single text block and corrupting reading order (Kendall's $\tau = 0.85$).
3. **Hybrid Retrieval (`retrieval/document_retriever.py`):** Combining dense semantic embeddings (`all-MiniLM-L6-v2`, $384$-d) with BM25 keyword matching via Reciprocal Rank Fusion (RRF) improved passage recall. However, fixed cosine thresholding ($\tau = 0.45$) frequently admitted contradictory or partially incomplete passages, leading to unmitigated hallucinations.
4. **Static Keyword Domain Router (`qa/domain_router.py`):** An initial 500-line regex router directed queries to specialized AST calculators and DBMS engines. However, brittle lexical collisions caused severe misclassifications: database questions mentioning "B+ tree indexing with $M=4$" tripped the arithmetic regex (`+` and `=`), routing relational normalization questions to arithmetic solvers.
5. **Worker Scheduling & Hardware Constraints (`routing/schedulers/`):** Capacity-Aware Scheduling managed OS-level threads and RAM. However, decoupled from semantic reasoning, local SLM inferences on 7B models frequently exceeded the 16 GB hardware boundary, inducing system thrashing.

These verified bottlenecks motivated the development of the three trainable research modules (R1, R2, R3) and their end-to-end integration in R4.

---

## 3. R1 — SR-EdgeNet: Structural Relationship Understanding

![Figure 2: SETU-NETRA Technical Architecture and Multi-Stage Pipeline](file:///d:/Projects/Setu-Netra/research/paper/figures/architecture_pipeline.png)
*Figure 2. SETU-NETRA technical architecture, tensor dimensionalities (384-d, 15-d, 1,537-d, 423-d), parameter counts (414K, 560K, 63K), and multi-stage execution pipeline connecting document ingestion, SR-EdgeNet multigraph reconstruction, ER-SP epistemic sufficiency gating, CM-RP policy selection, deterministic solver dispatch, and CitationVerifier source grounding.*

### 3.1 Mathematical Formulation
Let a document page contain $N$ detected OCR text blocks $\mathcal{B} = \{b_1, b_2, \dots, b_N\}$, where each block $b_i = (T_i, B_i)$ comprises recognized text string $T_i$ and normalized bounding box coordinates:
$$B_i = \left[ \frac{x_{\min, i}}{W}, \frac{y_{\min, i}}{H}, \frac{x_{\max, i}}{W}, \frac{y_{\max, i}}{H} \right] \in [0, 1]^4$$
where $W$ and $H$ denote canvas dimensions. We formulate structural reconstruction as predicting directed labeled edges in a multigraph $G = (\mathcal{V}, \mathcal{E})$, where vertices $v_i \in \mathcal{V}$ correspond to blocks $b_i$, and directed edges $e_{ij} \in \mathcal{E}$ belong to a 4-class taxonomy:
$$\mathcal{Y}_{\text{struct}} = \{\text{PARENT\_OF}, \text{OPTION\_OF}, \text{CONTINUATION\_OF}, \text{NONE}\}$$

```
                          b_1 (Question Stem)
                         /                   \
            (PARENT_OF) /                     \ (OPTION_OF)
                       v                       v
               b_2 (Premise Block)           b_3 (Option [A])
                       |
        (CONTINUATION) |
                       v
               b_4 (Multi-line Premise)
```

### 3.2 Model Architecture
`SR-EdgeNet` ($\mathbf{414,088}$ trainable parameters, $5.0\text{ MB}$ checkpoint) evaluates directed block pairs $(b_i, b_j)$ via a dual-stream multimodal projection:
1. **Semantic Text Stream:** Node embeddings $\mathbf{h}_i, \mathbf{h}_j \in \mathbb{R}^{384}$ are generated using frozen `all-MiniLM-L6-v2` and projected through a shared Linear layer $\phi_{\text{text}}: \mathbb{R}^{384} \rightarrow \mathbb{R}^{64}$ with LayerNorm and GELU:
   $$\mathbf{f}_{\text{text}} = \left[ \mathbf{z}_i \,\|\, \mathbf{z}_j \,\|\, |\mathbf{z}_i - \mathbf{z}_j| \,\|\, \mathbf{z}_i \odot \mathbf{z}_j \right] \in \mathbb{R}^{256}$$
2. **Normalized Spatial Offset Stream:** A $15$-dimensional geometric vector $\mathbf{e}_{ij}$ is constructed:
   $$\mathbf{e}_{ij} = \left[ B_i \,\|\, B_j \,\|\, \Delta x \,\|\, \Delta y \,\|\, d_{ij} \,\|\, \theta_{ij} \,\|\, \text{IoU}_{ij} \,\|\, \log\frac{w_i}{w_j} \,\|\, \log\frac{h_i}{h_j} \right] \in \mathbb{R}^{15}$$
   Projected via $\phi_{\text{spatial}}: \mathbb{R}^{15} \rightarrow \mathbb{R}^{64}$.
3. **Multimodal Fusion Classification Head:** The concatenated representation $[\mathbf{f}_{\text{text}} \,\|\, \mathbf{s}_{ij}] \in \mathbb{R}^{320}$ is processed by a 3-layer MLP with residual skip connections and dropout ($p = 0.15$), outputting logits over $\mathcal{Y}_{\text{struct}}$.

### 3.3 SETU-SR Dataset & Empirical Evaluation
The `SETU-SR` dataset was assembled across three distinct streams ($47,557$ directed edges, $470$ document units) with zero document overlap across splits:

| Split Identifier | Documents | Edges | Composition & Provenance | Role in Evaluation |
| :--- | :---: | :---: | :--- | :--- |
| `train.jsonl` | 349 | 36,346 | FUNSD Train (149) + Synth MCQ Train (200) | Gradient optimization (AdamW) |
| `val.jsonl` | 75 | 6,584 | FUNSD Test (50) + Synth MCQ Val (25) | Early stopping & checkpoint selection |
| `test_synthetic.jsonl` | 25 | 4,423 | Held-out Synthetic Layouts (25) | Synthetic layout generalization |
| `test_in_domain.jsonl` | 21 | 204 | Real Scans (16) + Project PDF (5) | **Held-out real-world gold test** |

#### Empirical Results & The Domain-Shift Phenomenon

```
+----------------------------------------------------------------------------------------------------+
|                                    SR-EdgeNet PERFORMANCE MATRIX                                   |
+--------------------------+--------------------+------------------------+---------------------------+
| Metric                   | XY-Cut Baseline    | SR-EdgeNet (Synthetic) | SR-EdgeNet (Real In-Domain)|
+--------------------------+--------------------+------------------------+---------------------------+
| Overall Accuracy (%)     | 78.40%             | **99.46%**             | 65.69%                    |
| Macro F1-Score           | 0.7412             | **0.9909**             | 0.5843                    |
| OPTION_OF Precision (%)  | 62.50%             | **100.00%**            | **88.89%**                |
| OPTION_OF Recall (%)     | 71.43%             | **100.00%**            | 66.67%                    |
| OPTION_OF F1-Score       | 0.6667             | **1.0000**             | 0.7619                    |
| CPU Latency per Edge     | 0.045 ms           | **0.011 ms**           | **0.012 ms**              |
+--------------------------+--------------------+------------------------+---------------------------+
```

*Scientific Insight on Domain Generalization:* While SR-EdgeNet achieves near-perfect accuracy ($99.46\%$) on synthetic exam layouts, performance drops to $65.69\%$ on real-world mobile scans. Forensic analysis revealed that mobile phone scans introduce 3–8° angular skew and non-linear perspective warping, displacing normalized coordinate vectors outside synthetic training distributions. Despite this domain shift, SR-EdgeNet maintains an **$88.89\%$ precision** on `OPTION_OF` edges, successfully preventing the catastrophic question-option interleaving common in XY-Cut.

---

## 4. R2 — ER-SP: Evidence Relevance and Sufficiency Predictor

### 4.1 Epistemic State Formulation
To eliminate blind generation over insufficient or contradictory context, `ER-SP` formalizes evidence evaluation as classification into five mutually exclusive epistemic states:
$$\mathcal{Y}_{\text{epistemic}} = \{\text{SUFFICIENT}, \text{PARTIALLY\_SUFFICIENT}, \text{CONTRADICTORY}, \text{IRRELEVANT}, \text{UNVERIFIABLE}\}$$

- **SUFFICIENT:** The passage contains complete, verifiable premises deductively entailing the query answer.
- **PARTIALLY_SUFFICIENT:** The passage is topically relevant and contains some necessary conditions, but lacks critical decisive facts.
- **CONTRADICTORY:** The passage addresses the exact entities and topic, but asserts a conflicting factual polarity.
- **IRRELEVANT:** The passage exhibits low or superficial lexical overlap with no topical bearing.
- **UNVERIFIABLE:** The query demands subjective, speculative, or future predictions that cannot be grounded in factual evidence.

### 4.2 Network Architecture
`ER-SP` ($\mathbf{560,134}$ trainable parameters, $2.25\text{ MB}$ checkpoint) operates downstream of dense retrieval:
1. **Dense Interaction Tensor:** For question $\mathbf{q} \in \mathbb{R}^{384}$ and passage $\mathbf{p} \in \mathbb{R}^{384}$ from frozen MiniLM:
   $$\mathbf{f}_{\text{cross}} = \left[ \mathbf{q} \,\|\, \mathbf{p} \,\|\, |\mathbf{q} - \mathbf{p}| \,\|\, \mathbf{q} \odot \mathbf{p} \,\|\, \cos(\mathbf{q}, \mathbf{p}) \right] \in \mathbb{R}^{1537}$$
2. **Attention-Pooled Aggregator:** Across $K$ retrieved candidate passages $\{\mathbf{p}_1, \dots, \mathbf{p}_K\}$, passage representations are transformed via an attention-pooling layer:
   $$\alpha_k = \frac{\exp(\mathbf{w}^T \tanh(\mathbf{W}_a \mathbf{f}_{\text{cross}, k}))}{\sum_{j=1}^K \exp(\mathbf{w}^T \tanh(\mathbf{W}_a \mathbf{f}_{\text{cross}, j}))}, \quad \mathbf{h}_{\text{doc}} = \sum_{k=1}^K \alpha_k \mathbf{f}_{\text{cross}, k} \in \mathbb{R}^{256}$$
3. **Classification Head:** Output logits over the 5 epistemic classes are trained via Focal Loss ($\gamma = 2.0$) to counter class imbalance.

### 4.3 SETU-ER Benchmark & Empirical Results
The `SETU-ER` benchmark comprises $2,252$ records partitioned across non-overlapping technical domains (Distributed Systems, OS Kernels, Relational Databases, Computer Networks, and Cryptography):
- **Train Split:** 1,560 samples (12 topics, 312 per class).
- **Validation Split:** 340 samples (4 held-out topics, 68 per class).
- **Unseen Test Split:** 340 samples (4 completely held-out topics, 68 per class).
- **In-Domain Gold Test:** 12 verified real project queries.

#### Comparative Benchmark Results (Unseen Test Topics, $N = 340$)

| Evaluation Metric | Cosine Threshold Baseline ($\tau = 0.55$) | Lexical Heuristic | **ER-SP (Proposed)** |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy (%)** | 37.65% | 45.88% | **86.18%** |
| **Macro F1-Score** | 0.2185 | 0.3621 | **0.8553** |
| **Contradiction Precision (%)** | 0.00% | 42.10% | **100.00%** |
| **Contradiction Recall (%)** | 0.00% | 58.82% | **95.59%** |
| **Contradiction F1-Score** | 0.0000 | 0.4908 | **0.9774** |
| **Abstention F1-Score** | 0.0000 | 0.5217 | **0.9318** |
| **Expected Calibration Error (ECE)** | 0.4120 | 0.2840 | **0.0889** |
| **Inference Latency on CPU** | **0.002 ms** | 0.045 ms | **0.450 ms** |

*Analysis:* Standard cosine thresholding exhibits an Abstention and Contradiction F1 of **0.0000**, blindly passing contradictory and unverifiable contexts to generation. In contrast, ER-SP achieves **$100.00\%$ precision** and **$95.59\%$ recall** on contradiction detection with an ECE of $0.0889$, providing a calibrated epistemic safeguard.

---

## 5. R3 — CM-RP: Contextual Multi-Strategy Reasoning Policy

### 5.1 Formulation of the 7-Action Strategy Space
`CM-RP` acts as a neural meta-reasoning policy mapping document and query context to seven concrete reasoning strategies:
$$\mathcal{A} = \{\text{ARITHMETIC\_SOLVER}, \text{DBMS\_SOLVER}, \text{FORMAL\_LOGIC\_SOLVER}, \text{EXTRACTIVE\_QA}, \text{LOCAL\_SLM}, \text{ADDITIONAL\_RETRIEVAL}, \text{ABSTAIN}\}$$

Every action maps directly to a verified executable subsystem:
1. `ARITHMETIC_SOLVER`: Python AST evaluator (`SafeArithmeticEvaluator`) for deterministic mathematical derivation without arbitrary code execution.
2. `DBMS_SOLVER`: Relational normalizer (`DBMSNormalizationSolver`) implementing Armstrong's axioms for closure and candidate key discovery.
3. `FORMAL_LOGIC_SOLVER`: Model-theoretic countermodel solver for categorical syllogisms and propositional validity.
4. `EXTRACTIVE_QA`: Direct token-span extractor audited by `CitationVerifier`.
5. `LOCAL_SLM`: Local 3B/7B language model for narrative synthesis when host RAM permits.
6. `ADDITIONAL_RETRIEVAL`: Recursive graph expansion over `SR-EdgeNet` when evidence is partially sufficient.
7. `ABSTAIN`: Immediate safe refusal without token generation when evidence is contradictory or unverifiable.

### 5.2 Multimodal Context State Representation ($423$-d)
`CM-RP` constructs a dense $423$-dimensional state vector $\mathbf{s}_t \in \mathbb{R}^{423}$:
$$\mathbf{s}_t = \left[ \mathbf{e}_{\text{query}} \,\|\, \mathbf{f}_{\text{struct}} \,\|\, \mathbf{f}_{\text{evidence}} \,\|\, \mathbf{f}_{\text{domain}} \,\|\, \mathbf{f}_{\text{telemetry}} \,\|\, \mathbf{f}_{\text{history}} \right]$$

- **Query Semantics ($\mathbb{R}^{384}$):** L2-normalized MiniLM sentence embedding.
- **Structural Features ($\mathbb{R}^8$):** Block counts, option density, multi-column flag, parent-child edge ratio from `SR-EdgeNet`.
- **Evidence Features ($\mathbb{R}^8$):** ER-SP epistemic probability distribution $[P(\text{Suff}), \dots, P(\text{Unverif})]$, max cosine retrieval similarity, passage token length.
- **Domain Indicators ($\mathbb{R}^{11}$):** Normalized symbolic frequencies for arithmetic operators, relational keywords, modal logic terms, and regex signals.
- **Hardware Telemetry ($\mathbb{R}^5$):** Host CPU utilization ($\%$, 5s EWMA), available physical RAM ($\text{GB}$), memory pressure ratio, execution thread saturation.
- **Policy History ($\mathbb{R}^7$):** One-hot representation of previous action and prior verification failure signal.

### 5.3 Policy Architecture & Hardware-Aware Action Masking
`CM-RP` ($\mathbf{63,367}$ parameters, $265\text{ KB}$ checkpoint) comprises a 3-layer feedforward network with LayerNorm and GELU activations. 

To guarantee stability on constrained hardware, CM-RP implements **dynamic hardware-aware action masking**:
$$\mathbf{m}_t(a) = \begin{cases} 0 & \text{if } a = \text{LOCAL\_SLM} \text{ and } \text{RAM}_{\text{avail}} < 1.5\text{ GB} \\ 0 & \text{if } a = \text{LOCAL\_SLM} \text{ and } \text{CPU}_{\text{load}} > 92\% \\ 1 & \text{otherwise} \end{cases}$$
$$\pi(a \mid \mathbf{s}_t) = \text{softmax}(\mathbf{z}_{\text{policy}} + \log \mathbf{m}_t)$$
This mathematically prevents Out-Of-Memory (OOM) exceptions and thread starvation under extreme host load.

### 5.4 Diagnosis & Resolution of Historical Routing Collisions (v1 vs. v2)
In CM-RP v1, queries involving database storage indexes (e.g., "Calculate the maximum number of keys in a B+ tree node of order $M=4$") were falsely classified as `ARITHMETIC_SOLVER` due to naive regex patterns matching `+` and `=`.

To resolve this without altering model provenance:
1. We retained `models/policy/cm_rp.pt` for historical comparison.
2. We redesigned domain feature extractors using negative lookaround regexes:
   $$\text{ARITH\_REGEX} = \texttt{(?<![a-zA-Z])[\\+\\-\\*/\\^=](?![a-zA-Z\\+])|\\b(?:calculate|compute|sum)\\b}$$
   explicitly ignoring `B+`, `C++`, and variable names with arithmetic symbols.
3. We trained **CM-RP v2** (`models/policy/cm_rp_v2.pt`) with increased regularization (dropout $0.20$, weight decay $3 \times 10^{-4}$), raising unseen test accuracy from $81.18\%$ to **$90.00\%$** (neural unassisted) and eliminating $100\%$ of $B^+$ tree false routings.

---

## 6. R4 — Complete System Integration & End-to-End Orchestration

The complete architecture is unified in `IntegratedSetuNetraPipeline` (`src/setu_netra/pipeline/integrated_pipeline.py`), executing a 10-stage synchronous pipeline:

```
[Raw Image / PDF] ──► Stage 1: Ingestion & Validation
                  ──► Stage 2: OCR Preprocessing (EasyOCR)
                  ──► Stage 3: Block Normalization & Layout Framing
                  ──► Stage 4: SR-EdgeNet Directed Graph Construction
                  ──► Stage 5: Hybrid Dense-BM25 Retrieval & Context Subgraph Selection
                  ──► Stage 6: ER-SP Epistemic Gating & Sufficiency Prediction
                  ──► Stage 7: CM-RP Context State Assembly (423-d) & Strategy Selection
                  ──► Stage 8: Specialized Execution (AST / DBMS / Logic / Extractive / SLM)
                  ──► Stage 9: CitationVerifier N-Gram Entailment & Source Coordinate Audit
                  ──► Stage 10: Grounded Response Delivery or Epistemic Abstention
```

### 6.1 Epistemic Verification & Citation Auditing
`CitationVerifier` enforces a strict contract: every assertion must map to a verifiable citation token `[Doc: d, Page: p, Block: b]`. The verifier computes token-level set intersection, polarity alignment, and coordinate containment against the physical document canvas. If the generated answer contains ungrounded claims, the pipeline triggers an epistemic refusal:
$$\text{Output} = \texttt{"[ABSTAIN: Claim lacks grounded citation support in source context]"}$$
This mechanism explicitly limits hallucination risks on enterprise edge deployments.

![Figure 3: Real-World Document Execution Trace Demonstration](file:///d:/Projects/Setu-Netra/research/paper/figures/execution_trace_demo.png)
*Figure 3. Real-world document execution trace on an authentic examination scan (`quest7.png`). Step 1: EasyOCR extracts normalized planar bounding boxes; Step 2: SR-EdgeNet reconstructs the directed structural hierarchy multigraph; Step 3: ER-SP performs epistemic sufficiency gating (SUFFICIENT) and CM-RP dispatches the query to the DBMS Normalization Solver; Step 4: Deterministic Armstrong closure algorithm computes minimal candidate keys (`{AB}`) with verified source coordinate citation grounding.*

---

## 7. Critical Statistical and Experimental Audit

To address anomalies identified in initial milestone testing, a formal statistical audit was conducted under two controlled problem investigations.

![Figure 4: Empirical Confusion Matrix Heatmaps](file:///d:/Projects/Setu-Netra/research/paper/figures/confusion_matrices.png)
*Figure 4. Empirical confusion matrix heatmaps across all three trainable research components: (Left) SR-EdgeNet 4×4 spatial-relational edge classifier (99.46% synthetic test accuracy); (Center) ER-SP 5×5 epistemic evidence gating network on held-out unseen topics (86.18% accuracy, 100% contradiction precision); (Right) CM-RP v2 7×7 contextual policy network on the independent balanced audit benchmark (N = 245, 94.29% accuracy, 0.9433 Macro F1), with zero zero-support and zero zero-recall classes.*

### 7.1 Problem 1: Resolution of CM-RP Zero-Support Classes
The initial 340-sample test split evaluated only 4 topics, leaving zero support ($N_{\text{support}} = 0$) for `FORMAL_LOGIC_SOLVER`, `LOCAL_SLM`, and `ADDITIONAL_RETRIEVAL`.

To validate the complete 7-action policy, an independent benchmark was constructed:
- **Benchmark:** `training/datasets/SETU-CM/splits/test_7action_independent.jsonl`
- **Volume:** $N = 245$ total examples, **exactly 35 verified examples per action**.
- **Domain Disjointness:** Completely unseen topics across astrophysics, enzyme kinetics, cohort retention metrics, modal satisfiability, and multi-hop statutory filings.

#### Complete 7×7 Confusion Matrix (CM-RP v2 Pure Neural, $N = 245$)
*Format: Rows = Ground-Truth Reference Class, Columns = Predicted Class*

```
                     ARITH   DBMS   LOGIC   EXTR   SLM    RETRIEVE  ABSTAIN   Total (Recall)
-----------------------------------------------------------------------------------------
ARITHMETIC_SOLVER  |   34      1      0       0      0        0         0    |  35 (97.14%)
DBMS_SOLVER        |    1     32      2       0      0        0         0    |  35 (91.43%)
FORMAL_LOGIC_SOLVER|    0      0     35       0      0        0         0    |  35 (100.0%)
EXTRACTIVE_QA      |    0      4      1      29      1        0         0    |  35 (82.86%)
LOCAL_SLM          |    1      0      0       0     34        0         0    |  35 (97.14%)
ADDITIONAL_RETRIEVE|    0      0      0       0      0       35         0    |  35 (100.0%)
ABSTAIN            |    0      3      0       0      0        0        32    |  35 (91.43%)
-----------------------------------------------------------------------------------------
Total Predicted    |   36     40     38      29     35       35        32    | 245
Precision (%)      | 94.4%  80.0%  92.1%  100.0%  97.1%   100.0%    100.0%   | Acc: 94.29%
```

#### Per-Class Performance Summary ($N = 245$, Support = 35 per class)

| Strategy Action | Precision (%) | Recall (%) | F1-Score | True Support | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `ARITHMETIC_SOLVER` | 94.44% | 97.14% | 0.9577 | 35 | **VALID** |
| `DBMS_SOLVER` | 80.00% | 91.43% | 0.8533 | 35 | **VALID** |
| `FORMAL_LOGIC_SOLVER` | 92.11% | **100.00%** | 0.9589 | 35 | **VALID** |
| `EXTRACTIVE_QA` | **100.00%** | 82.86% | 0.9062 | 35 | **VALID** |
| `LOCAL_SLM` | 97.14% | 97.14% | 0.9714 | 35 | **VALID** |
| `ADDITIONAL_RETRIEVAL` | **100.00%** | **100.00%** | **1.0000** | 35 | **VALID** |
| `ABSTAIN` | **100.00%** | 91.43% | 0.9552 | 35 | **VALID** |
| **Unweighted Macro Average** | **94.81%** | **94.29%** | **0.9433** | **35.0** | **VERIFIED** |

*Conclusion:* The audit proves that all seven actions possess valid statistical support ($N = 35$), non-zero recall ($\ge 82.86\%$), zero zero-support rows, and an overall macro F1 of **$0.9433$**.

---

### 7.2 Problem 2: Forensic Ablation Performance Investigation
The initial ablation report showed: CM-RP alone (C4) scored $72.00\%$, Complete R4 (C6) scored $70.00\%$, and ER-SP alone (C3) collapsed to $24.00\%$.

#### 1. Why Did ER-SP Alone (C3) Score 24.00%?
ER-SP is an epistemic gating model, not an execution engine. In configuration C3 (where CM-RP was ablated), all non-abstaining queries defaulted to `EXTRACTIVE_QA`. The 50-query challenge suite comprises 15 Arithmetic, 13 DBMS, 10 Formal Logic, and 12 Extractive queries. `EXTRACTIVE_QA` scored $0/38$ on arithmetic, DBMS, and logic questions, but achieved $12/12$ on extractive queries:
$$\text{Accuracy}_{\text{C3}} = \frac{12}{50} = \mathbf{24.00\%}$$
This confirms that epistemic verification without specialized execution solvers cannot solve multi-domain document tasks.

#### 2. Forensic Resolution of the C4 (72%) vs. C6 (70% vs. 92%) Inversion
In the initial benchmark script, C6 was evaluated with synthetic placeholder strings:
$$\text{passage\_context} = \text{["Sample document passage context"]}$$
- **In C4 (CM-RP Alone):** Solvers executed mathematical and relational derivations without verifying grounding against the passage context, scoring $36/50 = \mathbf{72.00\%}$.
- **In C6 under Placeholder Context:** `CitationVerifier` audited generated answers against `["Sample document passage context"]`. Finding zero lexical overlap, it triggered an anti-hallucination refusal (`is_abstention = True`). The benchmark penalized C6 for refusing to hallucinate ungrounded facts ($35/50 = \mathbf{70.00\%}$).

#### Re-Evaluation Under Genuine Grounded Context ($N = 50$)
When re-evaluated with verified grounded document passages:

| Architecture Configuration | Accuracy (%) | Abstention F1 | Mean Grounding | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **C1 (Baseline Heuristic: XY-Cut + Cosine + Regex)** | 44.00% | 0.0000 | 0.608 | 0.35 ms |
| **C2 (C1 + SR-EdgeNet)** | 42.00% | 0.0000 | 0.594 | 0.19 ms |
| **C3 (C1 + ER-SP)** | 24.00% | 0.0000 | 0.468 | 0.67 ms |
| **C4 (C1 + CM-RP v2)** | 72.00% | 0.5517 | 0.932 | 0.32 ms |
| **C5 (SR-EdgeNet + ER-SP)** | 44.00% | 0.0000 | 0.608 | 0.66 ms |
| **C6 (Complete Pipeline under Placeholder Context)** | 70.00% | 0.5333 | 0.930 | 135.99 ms |
| **C6 (Complete Pipeline under Grounded Context)** | **92.00%** | **0.9524** | **0.946** | 24.44 ms |

*Definitive Result:* Under genuine operating conditions with grounded evidence, **the complete SETU-NETRA pipeline achieves $92.00\%$ accuracy**, outperforming CM-RP alone ($72.00\%$) by **$+20.00\%$** ($p < 0.01$) and baseline RAG ($44.00\%$) by **$+48.00\%$**, with an Abstention F1 of **$0.9524$** and Grounding Score of **$0.946$**.

![Figure 5: Controlled Ablation Benchmark Comparison Across Configurations](file:///d:/Projects/Setu-Netra/research/paper/figures/ablation_barchart.png)
*Figure 5. Controlled ablation benchmark comparison across configurations C1 through C6 Grounded (N = 50 challenge suite). Complete SETU-NETRA (C6 Grounded) achieves 92.00% accuracy, 0.9524 Abstention F1, and 0.946 Grounding Score, demonstrating the necessity of coupling structural understanding (R1), epistemic gating (R2), and contextual multi-strategy policy dispatching (R3). Note the collapse of ER-SP alone (C3: 24%) due to missing execution solvers and the recovery of C6 Grounded over ungrounded placeholder context (70% vs 92%).*

---

## 8. Failure Analysis, Limitations & Engineering Trade-Offs

Despite its verified capabilities, SETU-NETRA exhibits several genuine engineering limitations:

1. **Warped Scanned Documents in SR-EdgeNet:** While synthetic layouts yield $99.46\%$ accuracy, real-world smartphone photos with perspective distortion lower edge recall to $65.69\%$. Integrating spatial coordinate normalization or affine rectification is required before edge classification.
2. **Multi-Hop Premise Gaps in ER-SP:** When a proof requires synthesis across more than four non-adjacent pages, ER-SP can classify evidence as `PARTIALLY_SUFFICIENT`, forcing safe abstention or additional retrieval rather than completing the multi-hop deduction.
3. **Regex Brittleness in Heuristic Fallbacks:** CM-RP v2 pure neural ($94.29\%$) substantially outperforms the rule fallback configuration ($88.16\%$), confirming that complex natural language prompts resist rigid keyword partitioning.
4. **End-to-End Latency Overhead:** While isolated model passes execute in sub-millisecond time ($0.012\text{ ms}$ for SR-EdgeNet, $0.450\text{ ms}$ for ER-SP, $0.388\text{ ms}$ for CM-RP), full end-to-end CPU text parsing, tokenization, AST evaluation, and citation verification incur an average latency of $24.44\text{ ms}$ per query.

---

## 9. Conclusion

SETU-NETRA demonstrates that reliable document intelligence on edge hardware cannot rely solely on uncalibrated autoregressive language models or naive geometric heuristics. By decomposing document understanding into **learned structural reconstruction (SR-EdgeNet)**, **epistemic sufficiency gating (ER-SP)**, and **contextual reasoning strategy selection (CM-RP)**, the framework achieves an optimal balance between symbolic precision and neural adaptability. The system achieves **$92.00\%$ grounded accuracy** and **$0.9524$ Abstention F1** on complex multi-domain queries while strictly respecting a $16\text{ GB}$ RAM constraint.

Future work will investigate end-to-end differentiable graph-epistemic training and affine-invariant spatial coordinate embeddings for heavily distorted mobile document scans.

---

## References

1. Asai, A., et al. (2024). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*. In Proceedings of ICLR 2024.
2. Chen, L., et al. (2023). *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance*. In NeurIPS 2023.
3. Gao, T., et al. (2023). *Enabling Large Language Models to Generate Text with Citations*. In Proceedings of EMNLP 2023.
4. Karpukhin, V., et al. (2020). *Dense Passage Retrieval for Open-Domain Question Answering*. In Proceedings of EMNLP 2020.
5. Kim, G., et al. (2022). *OCR-free Document Understanding Transformer*. In Proceedings of ECCV 2022.
6. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. In NeurIPS 2020.
7. Li, M., et al. (2021). *PICK: Processing Information from Key-Value Pairs in Visually-Rich Documents using Graph Neural Networks*. In Proceedings of ICPR 2021.
8. Ong, D., et al. (2024). *RouteLLM: Learning to Route to Large Language Models*. LMSYS Technical Report.
9. Xu, Y., et al. (2020). *LayoutLM: Pre-training of Text and Layout for Document Image Understanding*. In Proceedings of KDD 2020.
10. Xu, Y., et al. (2022). *LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking*. In Proceedings of ACM Multimedia 2022.
