# SETU-NETRA V1.1 Baseline Experimental Protocol
## Methodological Framework, 2x2 Factorial Design, and Statistical Validation Suite

> **Document ID:** SETU-NETRA-V1.1-EXP-PROTO-001  
> **Target Version:** V1.1 Baseline Infrastructure  
> **Status:** RATIFIED & EMPIRICALLY EXECUTED  
> **Date:** November 10, 2026  
> **Author:** Senior AI Systems Benchmarking Engineer & Experimental Researcher  
> **Environment Manifest:** [`benchmarks/v1_1/manifest.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/manifest.json)  
> **Master Aggregated Data:** [`benchmarks/v1_1/data/aggregated_baseline_results.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/data/aggregated_baseline_results.json)  

---

## 1. Primary Research Question & Scope Boundaries

### 1.1 Formal Research Question
```
Can decoupled adaptive model routing and capacity-aware worker scheduling 
improve evidence-grounded document question answering under consumer-hardware constraints?
```

### 1.2 Sub-Hypotheses
* **$H_{1}$ (Routing Quality & Latency Hypothesis):** Adaptive intent routing dynamically dispatches factual, direct extraction queries to specialized deterministic extractive engines and synthesis queries to small language models (SLMs), significantly increasing Token F1, Citation Precision, and reducing median end-to-end latency compared to a static generative SLM.
* **$H_{2}$ (Worker Scheduling Tail Hypothesis):** Under concurrent arrival load, Capacity-Aware Scheduling (CAS) that accounts for worker queue depth, hardware load, and model execution profiles achieves lower $P_{99}$ tail latency, fewer SLO violations, and higher goodput than naive Round Robin dispatching.
* **$H_{3}$ (Orthogonal Interaction Hypothesis):** In the absence of concurrent queue contention (sequential execution), model routing dictates cognitive quality (F1, citations) while scheduling algorithm selection has zero effect on answer text; under load, routing and scheduling interact constructively to eliminate system saturation.

### 1.3 Strict Scope Boundaries
* **Source Code Invariance:** Zero modifications permitted to production application logic in `src/setu_netra/` or regression test suites in `tests/`.
* **Zero Synthetic Fabrication:** All reported metrics must originate from physical benchmark executions persisted as raw per-request records in `benchmarks/v1_1/data/`.
* **Hardware Containment:** Execution restricted to consumer laptop hardware (10-core Intel CPU, 16 GB physical RAM, no discrete GPU, PyTorch CPU backend).

---

## 2. 2×2 Full-Factorial Experimental Design

To isolate the independent effect of Model Routing, the independent effect of Worker Scheduling, and their potential interaction, the benchmark establishes a balanced 2×2 full-factorial design:

```
                          Factor B: Worker Scheduling Policy
                          ---------------------------------------------------
                          Level 0: Round Robin (RR) | Level 1: Capacity-Aware (CAS)
-------------------------+--------------------------+------------------------
Factor A:   Level 0:     | Condition A              | Condition B
Model       Fixed Model  | (Fixed SmolLM2 + RR)     | (Fixed SmolLM2 + CAS)
Routing     (SmolLM2)    |                          |
Policy      -------------+--------------------------+------------------------
            Level 1:     | Condition C              | Condition D
            Adaptive     | (Adaptive Routing + RR)  | (Adaptive Routing + CAS)
            Routing      |                          |
-------------------------+--------------------------+------------------------
```

### Condition Definitions & Configuration Files
1. **Condition A (`Condition_A`, Control Baseline):**
   * Config: [`benchmarks/v1_1/configs/condition_a_fixed_rr.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/configs/condition_a_fixed_rr.json)
   * Routing: Fixed model targeting `smollm2-135m-instruct`.
   * Scheduling: `RoundRobinScheduler`.
2. **Condition B (`Condition_B`, Isolated Scheduler Factor):**
   * Config: [`benchmarks/v1_1/configs/condition_b_fixed_cas.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/configs/condition_b_fixed_cas.json)
   * Routing: Fixed model targeting `smollm2-135m-instruct`.
   * Scheduling: `CapacityAwareScheduler`.
3. **Condition C (`Condition_C`, Isolated Routing Factor):**
   * Config: [`benchmarks/v1_1/configs/condition_c_adapt_rr.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/configs/condition_c_adapt_rr.json)
   * Routing: `AdaptiveModelRouter` (automatic cognitive intent dispatching).
   * Scheduling: `RoundRobinScheduler`.
4. **Condition D (`Condition_D`, Full Decoupled System):**
   * Config: [`benchmarks/v1_1/configs/condition_d_adapt_cas.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/configs/condition_d_adapt_cas.json)
   * Routing: `AdaptiveModelRouter` (automatic cognitive intent dispatching).
   * Scheduling: `CapacityAwareScheduler`.

---

## 3. Benchmark Corpus and Ground-Truth Evaluation Set

### 3.1 Benchmark Technical Corpus
The evaluation corpus is isolated from development data and loaded into a dedicated SQLite database (`output/v1_1_benchmark_store.db`):

| Document File | Domain | Topics Covered | Blocks Ingested |
| :--- | :--- | :--- | :--- |
| `doc_operating_systems.txt` | Systems Architecture | Virtual memory, MMU, hierarchical page tables, TLB hits/misses, demand paging, Belady's MIN, LRU Clock algorithm, thrashing, Working Set Model | 10 blocks (1 title, 9 content) |
| `doc_raft_consensus.txt` | Distributed Systems | Raft consensus, 3 subproblems, node states (Leader/Follower/Candidate), terms, randomized timeouts, majority quorums, heartbeat frequency (50ms), leader completeness, log compaction | 10 blocks (1 title, 9 content) |
| `doc_database_concurrency.txt` | Database Systems | ACID properties, 2PL growing/shrinking phases, Strict 2PL, Rigorous 2PL, wait-for cycle deadlock detection, ANSI isolation levels, MVCC/Snapshot Isolation, ARIES recovery (Analysis/Redo/Undo) | 10 blocks (1 title, 9 content) |

### 3.2 Curated 100-Query Evaluation Dataset
Stored in [`benchmarks/v1_1/queries/qa_evaluation_queries.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/queries/qa_evaluation_queries.json), the evaluation dataset comprises $N = 100$ ground-truth questions:
* **Operating Systems Sub-corpus:** 35 questions (`Q_OS_01` to `Q_OS_35`).
* **Raft Consensus Sub-corpus:** 35 questions (`Q_RAFT_01` to `Q_RAFT_35`).
* **Database Concurrency Sub-corpus:** 20 questions (`Q_DB_01` to `Q_DB_20`).
* **Negative / Unsupported Set:** 10 questions (`Q_UN_01` to `Q_UN_10`) targeting out-of-corpus topics (e.g., Paxos vs PBFT, quantum teleportation, B-tree split algorithms).

Each query record includes:
* `query_id`: Unique tracking identifier.
* `question`: Natural language user question.
* `document_name`: Target grounding document.
* `expected_block_ids`: List of exact passage `block_id` integers containing the ground-truth evidence.
* `reference_answer`: Golden standard extractive answer.
* `intent`: Cognitive task type (`FACTUAL`, `DEFINITION`, `PROCEDURAL`, `COMPARATIVE`).
* `is_supported`: Boolean flag (`True` for supported, `False` for unsupported questions).
* `expected_epistemic_status`: Expected verification state (`EVIDENCE_BACKED` vs `UNSUPPORTED`).

---

## 4. Evaluation Metrics and Mathematical Formulations

### 4.1 Answer Quality & Factuality Metrics
* **Exact Match (EM):**
  $$\text{EM} = \mathbb{I}(\text{norm}(y_{\text{pred}}) = \text{norm}(y_{\text{gold}}))$$
  where $\text{norm}(\cdot)$ lowercases, strips punctuation, and removes leading/trailing articles (`a`, `an`, `the`).

* **Token-Level F1 Score:**
  Let $P$ and $G$ be multiset token bags of normalized prediction and reference answer:
  $$\text{Precision} = \frac{|P \cap G|}{|P|}, \quad \text{Recall} = \frac{|P \cap G|}{|G|}$$
  $$\text{Token F1} = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} \quad (\text{with } F1=1.0 \text{ if } |P|=|G|=0)$$

* **Passage-Level Citation Precision:**
  $$\text{Citation Precision} = \frac{|\{c \in \text{Citations} \mid c.\text{block\_id} \in \text{ExpectedBlocks}\}|}{\max(1, |\text{Citations}|)}$$
  For unsupported queries ($\text{ExpectedBlocks} = \emptyset$), precision is $1.0$ if the system emits zero citations, $0.0$ otherwise.

* **Information Retrieval Metrics (at $K \in \{1, 3, 5\}$):**
  $$\text{Recall@}K = \frac{|\text{Retrieved}_{1:K} \cap \text{ExpectedBlocks}|}{|\text{ExpectedBlocks}|}$$
  $$\text{MRR} = \frac{1}{\min \{r \mid \text{Retrieved}[r] \in \text{ExpectedBlocks}\} \cup \{\infty\}}$$
  $$\text{nDCG@}3 = \frac{\text{DCG@}3}{\text{IDCG@}3}, \quad \text{DCG@}3 = \sum_{i=1}^{3} \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}$$

### 4.2 Latency, Tail Percentiles, and Queuing Telemetry
* **Total Latency ($L_{\text{total}}$):**
  $$L_{\text{total}} = T_{\text{retrieval}} + T_{\text{queue\_wait}} + T_{\text{execution}} + T_{\text{verification}}$$
* **Tail Percentiles ($P_{50}, P_{95}, P_{99}$):** Computed from empirical order statistics.
* **Non-Parametric Bootstrap Confidence Intervals:**
  For any percentile $\theta \in \{P_{50}, P_{95}, P_{99}\}$, $B = 1,000$ bootstrap resamples with replacement are drawn:
  $$\text{CI}_{95\%}(\theta) = [\theta^*_{0.025}, \, \theta^*_{0.975}]$$
* **Throughput & Goodput:**
  $$\text{Throughput} = \frac{N_{\text{total}}}{T_{\text{elapsed}}}, \quad \text{Goodput} = \frac{N_{\text{success}}}{T_{\text{elapsed}}}$$
* **Service Level Objective (SLO) Violation Rate:**
  Fraction of successful requests with $L_{\text{total}} > 500\,\text{ms}$.

---

## 5. Statistical Power and Analysis Models

### 5.1 Sample Size and Power Justification
* **Quality Benchmark ($N = 100$ repeated-measures queries):**
  For a repeated-measures design across 4 conditions on the same items, $N = 100$ provides $>85\%$ statistical power ($\beta < 0.15$) to detect small-to-medium effect sizes ($f \ge 0.15$) at significance level $\alpha = 0.05$.
* **Synthetic Load Benchmark ($N = 1,000$ requests per condition):**
  Estimation of tail percentiles ($P_{99}$) requires a large sample size. With $N = 1,000$, the 99th percentile represents the 10th highest observation, ensuring robust nonparametric bootstrap confidence intervals without small-sample tail collapse.

### 5.2 Statistical Testing Models
1. **$2 \times 2$ Repeated-Measures Factorial ANOVA:**
   Evaluated using orthogonal contrast decomposition on paired observations:
   * **Main Effect of Routing (Factor A):** $C_A = (y_{10} + y_{11}) - (y_{00} + y_{01})$
   * **Main Effect of Scheduling (Factor B):** $C_B = (y_{01} + y_{11}) - (y_{00} + y_{10})$
   * **Interaction Effect ($A \times B$):** $C_{AB} = (y_{11} - y_{10}) - (y_{01} - y_{00})$
   * Test statistic: One-sample $t$-test on contrast vectors ($t^2 = F(1, N-1)$) yielding exact $p$-values and partial eta-squared:
     $$\eta_p^2 = \frac{F}{F + \text{df}_{\text{error}}}$$
2. **McNemar's Test (Paired Binary Classifications):**
   Applied to discrete success/failure classifications between conditions using Edwards continuity correction:
   $$\chi^2 = \frac{(|b - c| - 1)^2}{b + c}, \quad \text{df} = 1$$
3. **Paired Wilcoxon Signed-Rank Test:**
   Non-parametric pairwise comparison for continuous scores (Token F1 and Latency) without assuming Gaussian distribution.

---

## 6. Execution Command and Manifest Linkage

The complete benchmark protocol is encapsulated in the master runner script and can be executed with:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python benchmarks/v1_1/runner.py --mode all
```

* **Environment Manifest:** [`benchmarks/v1_1/manifest.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/manifest.json)
* **Master Aggregated Dataset:** [`benchmarks/v1_1/data/aggregated_baseline_results.json`](file:///d:/Projects/Setu-Netra/benchmarks/v1_1/data/aggregated_baseline_results.json)
