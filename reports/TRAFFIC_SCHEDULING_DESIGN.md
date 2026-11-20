# SETU-NETRA: Intelligent AI Traffic Management & Worker Scheduling Design

**Report ID:** SETU-TRAFFIC-DESIGN-005  
**Date:** November 9, 2026  
**Audience:** System Architects, Core Developers, Evaluators  
**Scope:** Worker Pool Architecture, Telemetry Monitoring, Queue Scheduling, and Load Balancing Algorithms  

---

## 1. Executive Summary

While **Model Selection** determines *which* model architecture possesses the capabilities to satisfy a user request, **Worker Scheduling** resolves an entirely distinct operational problem: **Which available physical worker process or hardware resource should execute the inference?**

In high-concurrency production environments or resource-constrained local hardware, unmanaged execution causes queue congestion, memory exhaustion, severe tail latency spikes ($p99$), and cascading worker crashes. The **Intelligent AI Traffic Management Engine** acts as the centralized load balancer, queue manager, and telemetry monitor for SETU-NETRA.

---

## 2. Decoupled Two-Tier Architecture

```
                   +-------------------------------------------------------------+
                   |                 Incoming Inference Requests                 |
                   +-------------------------------------------------------------+
                                                  |
                                                  v
                   +-------------------------------------------------------------+
                   |             TIER 1: ADAPTIVE MODEL ROUTER                   |
                   |   - Query Complexity Analysis                               |
                   |   - Resolves Target Model ID (e.g., 'all-minilm-l6-v2')     |
                   +-------------------------------------------------------------+
                                                  |
                                                  v  (Target Model ID + Payload)
                   +-------------------------------------------------------------+
                   |             TIER 2: TRAFFIC MANAGEMENT ENGINE               |
                   |   - Central Request Priority Queue                          |
                   |   - Real-Time Hardware Telemetry Monitor                    |
                   |   - Worker Pool Health & State Tracker                      |
                   |   - Pluggable Scheduling Policy                             |
                   +-------------------------------------------------------------+
                                                  |
                                Dispatch to Scheduled Worker
                                                  v
                   +-------------------------------------------------------------+
                   |                     WORKER POOL REPLICAS                    |
                   |   +--------------------+     +--------------------+         |
                   |   | Worker 1 (Local)   |     | Worker 2 (Local)   |   ...   |
                   |   | - Inflight: 2      |     | - Inflight: 0      |         |
                   |   | - CPU: 42%         |     | - CPU: 15%         |         |
                   |   | - RAM: 180 MB      |     | - RAM: 90 MB       |         |
                   |   +--------------------+     +--------------------+         |
                   +-------------------------------------------------------------+
```

---

## 3. Worker Pool State Machine & Telemetry Node

Each inference worker $w \in \mathcal{W}$ runs as an isolated thread or subprocess with a monitored life cycle:

```
    [INIT] ---> (LOADING_WEIGHTS) ---> [HEALTHY / IDLE] <---> [BUSY]
                                              |                  |
                                        (Heartbeat Miss)   (OOM / Crash)
                                              v                  v
                                        [DEGRADED]  --->  [UNHEALTHY / RESTART]
```

### Monitored Worker Telemetry Metrics:
For every worker $w$, the scheduler tracks measurable physical metrics:
* $A_w$: Active inflight requests currently executing.
* $Q_w$: Pending queue length assigned to worker $w$.
* $\bar{T}_w$: Exponential Moving Average (EMA) of historical execution latency (ms).
  $$\bar{T}_w^{(t)} = \beta \cdot T_{\text{new}} + (1 - \beta) \cdot \bar{T}_w^{(t-1)}, \quad \beta = 0.20$$
* $\text{CPU}_w$: Operating system process CPU utilization ($[0.0, 100.0\%]$).
* $\text{RAM}_w$: Physical resident set size memory in megabytes (RSS MB).
* $F_w$: Cumulative request failure count.
* $\text{Status}_w$: `IDLE`, `BUSY`, `DEGRADED`, `UNHEALTHY`.

---

## 4. The Six Scheduling Algorithms: Mathematical Formulations

To evaluate scheduling performance empirically, SETU-NETRA implements six distinct, mathematically defined dispatching policies:

### 4.1 Algorithm 1: Round Robin (RR)
* **Principle:** Static cyclic assignment across eligible workers without inspecting load.
* **Formulation:** Maintain pointer $i \in \{0, 1, \dots, |\mathcal{W}| - 1\}$.
  $$w^* = \mathcal{W}[i], \quad i \leftarrow (i + 1) \pmod{|\mathcal{W}|}$$
* **Strengths:** Zero computational overhead ($O(1)$ dispatch).
* **Failure Mode:** Under heterogeneous query lengths, fast workers sit idle while slow workers accumulate backlogs (Convoy Effect).

---

### 4.2 Algorithm 2: Random Scheduling
* **Principle:** Stochastic uniform selection.
* **Formulation:**
  $$w^* \sim \mathcal{U}(\mathcal{W})$$
* **Strengths:** Eliminates deterministic synchronization locks.
* **Failure Mode:** High variance in tail latency ($p99$); vulnerable to assigning requests to already congested workers.

---

### 4.3 Algorithm 3: Least Outstanding Requests (LOR)
* **Principle:** Route to the worker with the minimum total pending and executing work.
* **Formulation:**
  $$w^* = \arg\min_{w \in \mathcal{W}_{\text{healthy}}} (A_w + Q_w)$$
  Ties broken randomly.
* **Strengths:** Dynamic load leveling; mathematically prevents severe queue imbalances under identical worker speeds.

---

### 4.4 Algorithm 4: Shortest Estimated Completion Time (SECT)
* **Principle:** Predict when a request will actually finish based on queue wait time and input prompt size.
* **Formulation:**
  $$\text{WaitTime}_w = Q_w \times \bar{T}_w$$
  $$\text{ExecTime}_w = \text{BaseLatency}_w + (\text{InputTokens} \times \text{TimePerToken}_w)$$
  $$\text{ECT}_w = \text{WaitTime}_w + \text{ExecTime}_w$$
  $$w^* = \arg\min_{w \in \mathcal{W}_{\text{healthy}}} \text{ECT}_w$$
* **Strengths:** Minimizes average response time (approximates Shortest Job First / SRPT). Effectively routes small queries around large generation jobs.

---

### 4.5 Algorithm 5: Capacity-Aware Scheduling (CAS)
* **Principle:** Incorporates real-time host hardware telemetry (CPU load and memory headroom) to prevent system thrashing and out-of-memory crashes.
* **Formulation:** Compute normalized worker capacity score $C_w \in [0.0, 1.0]$:
  $$C_w = \left( 1 - \frac{A_w}{\text{MaxConcurrency}_w} \right) \times \left( 1 - \frac{\text{CPU}_w}{100} \right) \times \left( \frac{\text{RAM\_Available\_MB}}{\text{RAM\_Total\_MB}} \right)$$
  * If $C_w \le 0.05$ for all workers: Trigger **Backpressure** (reject request with HTTP 429 / retry after $\Delta t$ rather than crashing the process).
  * Otherwise:
    $$w^* = \arg\max_{w \in \mathcal{W}_{\text{healthy}}} C_w$$

---

### 4.6 Algorithm 6: Adaptive Resilient Scheduling (ARS)
* **Principle:** Closed-loop feedback combining estimated completion time with worker reliability and error-rate penalties.
* **Formulation:**
  $$\text{Penalty}_w = 1.0 + 2.0 \cdot \left(\frac{F_w}{\text{TotalRequests}_w + 1}\right) + \mathbb{I}(\text{Status}_w == \text{DEGRADED}) \cdot 0.50$$
  $$\text{Score}_w = \text{ECT}_w \times \text{Penalty}_w$$
  $$w^* = \arg\min_{w \in \mathcal{W}_{\text{healthy}}} \text{Score}_w$$
* **Strengths:** Automatically routes traffic away from failing or degraded workers without requiring manual restart intervention.

---

## 5. Queueing Theory Foundations & Performance Metrics

The traffic subsystem models worker clusters using classical queueing approximations:

```
               Arrival Rate (lambda)                 Service Rate (mu)
      Requests -------------------> [ QUEUE ] -------------> [ WORKER ]
                                  Wait Time (W_q)          Service Time (S)
                                  \---------------------------------------/
                                            Total Latency (T = W_q + S)
```

By **Little's Law**:
$$L = \lambda \cdot W$$
Where $L$ is average requests in the system, $\lambda$ is request arrival rate, and $W$ is total residence time.

### Quantitative Benchmark Metrics Captured per Request:
1. **Queue Wait Time ($W_q$):** Milliseconds elapsed from arrival to execution start.
2. **Inference Latency ($S$):** Execution duration on physical hardware.
3. **Total Roundtrip Latency ($T = W_q + S$):** End-to-end user perceived delay.
4. **Latency Percentiles:** $p50$ (median), $p95$ (tail), $p99$ (worst-case).
5. **System Throughput:** Requests completed per second ($\text{RPS}$).
6. **Worker Utilization ($\rho$):** Fraction of time workers spend actively computing ($\rho = \frac{\lambda}{c \cdot \mu}$).
7. **Failure & Rejection Rate:** Percentage of dropped or timed-out requests.
