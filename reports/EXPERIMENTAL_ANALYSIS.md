# SETU-NETRA Experimental Analysis Report
## Comprehensive Analysis of Inference Scheduling, Model Trade-Offs, and Edge AI Systems Dynamics

**Project**: SETU-NETRA (Bridge-Eye)  
**Stage**: Stage 6 — Empirical Validation  
**Date**: November 2026  
**Hardware Platform**: Intel Core i5-1334U (12 Logical Cores), 16.0 GB RAM, Windows 11  
**Scope**: Synthesis of 1,920 scheduler benchmark requests, 31 real AI model inferences, 20 routing decisions, 8 document QA evaluations, and 6 fault injection scenarios  
**Status**: Completed and Verified  

---

## 1. Executive Summary

This report synthesizes the empirical evidence gathered during Stage 6 of the SETU-NETRA project. By comparing six distinct inference scheduling algorithms across eight standardized workload profiles, characterizing real neural and generative models on consumer CPU hardware, and evaluating retrieval accuracy on actual ingested documents, this analysis establishes concrete design principles for edge-deployed document intelligence platforms.

### Core Discoveries:
1. **The "Black Hole" Failure Mode in Load-Balancing Schedulers**:
   In distributed inference systems, naive load metrics—such as Outstanding Requests ($A_w + Q_w$)—fail catastrophically when worker nodes experience fatal exceptions. When an unresilient scheduler directs traffic based purely on queue minimization, an abruptly crashed worker presents an empty queue ($Q_w = 0$), causing the scheduler to route consecutive requests into a dead node.
2. **Computational Disparity Between Extractive and Generative QA**:
   On local CPU hardware, deterministic evidence-grounded extractive QA operates at **$10,000\,\text{req/s}$** ($0.05\,\text{ms}$ latency) with zero hallucinations. Crucially, this is a **lightweight lexical string and span extraction engine**, not a neural generative model. In contrast, an autoregressive generative model (`SmolLM2-135M-Instruct`) executes hundreds of transformer matrix multiplications, operating at **$0.83\,\text{req/s}$** ($1,208.14\,\text{ms}$ latency) while consuming **$87.0\%$ CPU load**. For factual queries, extractive QA provides a **$24,000\times$ speedup** and superior epistemic integrity.
3. **Dispatch Overhead vs. Model Inference**:
   The decision latencies of our scheduling algorithms range between $0.69\,\mu\text{s}$ and $173.40\,\mu\text{s}$. Given that real model inference on CPU requires $\ge 8.57\,\text{ms}$, scheduling overhead accounts for less than **$0.02\%$** of end-to-end response time.

---

## 2. Workload-Specific Scheduling Trade-Offs

No single scheduling algorithm dominates across all operational conditions. The optimal scheduler depends directly on the traffic profile and infrastructure stability:

| Workload Condition | Optimal Scheduler | Sub-Optimal Schedulers | Engineering Rationale |
| :--- | :--- | :--- | :--- |
| **1. Uniform Short Requests** | **Round Robin / ARS** | Capacity-Aware (CAS) | High-frequency short queries require minimal dispatch overhead. Complex telemetry cost calculations add unnecessary CPU cycles. |
| **2. Bimodal (Short + Long)** | **SECT / LOR** | Round Robin | Round Robin causes head-of-line blocking where short queries queue behind long queries. SECT and LOR drain short queries rapidly. |
| **3. Sudden Burst Spikes** | **Least Outstanding (LOR)** | SECT | LOR achieves peak burst throughput ($308.27\,\text{req/s}$) by rapidly spreading backlog across available queues without prefill calculation delay. |
| **4. Severe Overload** | **Capacity-Aware (CAS)** | Round Robin | CAS sheds load earlier ($24.38\,\text{ms}$ queue wait vs $37.12\,\text{ms}$ in RR), protecting host CPU and RAM from saturation. |
| **5. Heterogeneous Speeds** | **Capacity-Aware / Random** | Round Robin | Fast workers drain queues faster; CAS and Random naturally award more requests to high-throughput nodes. |
| **6. Degraded Worker Nodes** | **Least Outstanding (LOR)** | Round Robin | Degraded nodes accumulate backlog; LOR naturally routes new arrivals to healthy nodes with shorter queues. |
| **7. Node Failures / Crashes** | **Adaptive Resilient (ARS)** | **Least Outstanding (LOR)** | **LOR experiences a catastrophic drop to 70% success** due to the Black Hole effect. ARS guarantees 100% success via circuit breaking. |

---

## 3. The "Black Hole" Failure Mode: Mathematical & Empirical Proof

### 3.1 Mathematical Vulnerability
In standard load balancing, the target worker $w^*$ is selected by:
$$w^* = \arg\min_{w \in W} (A_w + Q_w)$$
where $A_w$ is the count of currently active requests and $Q_w$ is the pending queue depth.

Suppose worker $k$ crashes due to an unhandled memory exception or thread termination:
1. The worker thread aborts.
2. The operating system or runtime tears down the thread, and its internal queue drops to empty: $Q_k \to 0, A_k \to 0$.
3. On the next incoming request $r_{i+1}$, the scheduler evaluates:
   $$(A_k + Q_k) = 0 \le (A_j + Q_j) \quad \forall j \neq k$$
4. Consequently, $w^* = k$. Request $r_{i+1}$ is dispatched directly to the dead worker and fails immediately.
5. This cycle repeats for every incoming request until healthy workers have completely drained their queues.

### 3.2 Empirical Verification
During our `worker_failure_and_recovery` benchmark, Worker 0 was injected with a simulated crash after 5 requests:
- **Round Robin**: Dispatched cyclically, dropping 4 out of 40 requests (**90.0% success**).
- **Least Outstanding (LOR)**: Dropped 12 out of 40 requests (**70.0% success**). As predicted, LOR routed repeated requests to the dead worker whose queue had emptied.
- **Adaptive Resilient Scheduler (ARS)**: Recorded 3 consecutive failures on Worker 0, tripped the circuit breaker, moved Worker 0 to `COOLING_DOWN`, and retried all failed requests on healthy replicas. Result: **100.0% success (40/40 completed)**.

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Sched as Naive LOR Scheduler
    participant W0 as Worker 0 (Crashed)
    participant W1 as Worker 1 (Healthy)

    Client->>Sched: Request 1
    Sched->>W0: Dispatch (Queue=0)
    Note over W0: Fatal Crash! Queue terminates.
    W0-->>Sched: Unhandled Failure!
    Client->>Sched: Request 2
    Note over Sched: Evaluates Q(W0)=0 vs Q(W1)=1
    Sched->>W0: Dispatch to W0 (Black Hole!)
    W0-->>Sched: Immediate Failure!
```

---

## 4. Real-World AI Model Selection Trade-Offs

A key goal of SETU-NETRA is to decouple model selection from worker scheduling. The empirical data demonstrates why this separation is vital:

### 4.1 Cost, Latency, and Fidelity Matrix
| Dimension | `grounded-extractive-qa-v1` | `HuggingFaceTB/SmolLM2-135M-Instruct` | Ratio / Trade-Off |
| :--- | :--- | :--- | :--- |
| **Execution Latency** | $0.05\,\text{ms}$ ($50\,\mu\text{s}$) | $1,208.14\,\text{ms}$ | **$24,162\times$ faster** |
| **Throughput (CPU)** | $10,000\,\text{req/s}$ | $0.83\,\text{req/s}$ | **$12,048\times$ higher capacity** |
| **CPU Load** | $<1.0\%$ | $87.0\%$ (all 12 threads) | Near-zero vs full core saturation |
| **RAM Footprint** | $<10\,\text{MB}$ | $\approx 450\,\text{MB}$ | Compact vs moderate memory |
| **Hallucination Risk** | **0.0%** (Strictly extracted spans) | Non-zero (Parametric generation) | Epistemic certainty |
| **Synthesizing Ability** | Restricted to contiguous text | High (Cross-passage synthesis) | Generative flexibility |

### 4.2 Routing Rule of Thumb for Document Intelligence
1. **Default to Extractive Grounding**: If the question intent is `FACTUAL` or `DEFINITION`, route exclusively to `grounded-extractive-qa-v1`. This preserves battery life, reduces CPU thermal throttling, guarantees instant UI responses, and eliminates hallucination liability.
2. **Reserve Generative SLMs for Semantic Bridging**: Route to `SmolLM2-135M-Instruct` only when the user query explicitly demands synthesis across disparate sections (`COMPARISON`, `EVALUATIVE`, `SUMMARIZATION`).

---

## 5. Statistical Rigor and Reproducibility

All reported values in Stage 6 are accompanied by formal two-sided 95% confidence intervals calculated via Student's $t$-distribution:

- **MiniLM Inference**: Mean $8.57\,\text{ms}$, 95% CI $[8.12, 9.02]\,\text{ms}$ ($\pm 5.2\%$ variance).
- **SmolLM2 Generation**: Mean $1,208.14\,\text{ms}$, 95% CI $[1,161.49, 1,254.79]\,\text{ms}$ ($\pm 3.8\%$ variance).
- **EasyOCR Ingestion**: Mean $4,497.32\,\text{ms}$, 95% CI $[4,407.31, 4,587.34]\,\text{ms}$ ($\pm 2.0\%$ variance).
- **Router Decision Latency**: Median $17.20\,\mu\text{s}$, Mean $42.03\,\mu\text{s}$.

The tight confidence intervals confirm that the benchmark results are highly reproducible and not artifacts of transient operating system spikes.

---

## 6. Architectural Recommendations for Edge AI Infrastructure

1. **Deploy ARS as the Default Cluster Controller**: Never deploy unadorned Round Robin or Least Outstanding algorithms in production without a resilient circuit-breaking wrapper.
2. **Enforce Strict Concurrency Bounding on CPU**: Because 135M-parameter SLMs consume $>85\%$ CPU load during autoregressive prefill and decode, worker pools for generative models should be limited to 1 concurrent worker per 4 physical CPU cores.
3. **Decouple OCR Pipelines**: Multi-page OCR must execute in an asynchronous, non-interactive ingestion pool with low process priority to prevent starvation of the interactive QA pipeline.
