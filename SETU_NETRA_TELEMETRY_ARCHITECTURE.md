# SETU-NETRA: KORA KAAGAZ TELEMETRY ARCHITECTURE & EMPIRICAL OBSERVATION ENGINE
**System Version:** 2.0.0-RC1 (Kora Kaagaz Specification)  
**Document Classification:** Telemetry Architecture, Mathematical Specifications & Fluid Dynamics Model (Revised for V2.0.0-RC1 Corrections)  
**Author:** AI Systems Reliability & Performance Engineering  
**Date:** March 2026  

---

## 1. Architectural Philosophy: The Mandate of Truth

In accordance with the foundational ethos of **Kora Kaagaz** (The Pristine Parchment of Truth), SETU-NETRA strictly rejects synthetic telemetry, fabricated activity counters, simulated active users, or smoothed fake metrics.

Every pixel rendered on the **Live Intelligence Map** and every fluid particle simulated in **The Well** is an exact, deterministic reflection of underlying operating system hardware counters (`kernel32.dll` on Windows), genuine Python thread allocations, actual model inference token intervals, and live database transactions.

If zero queries are being submitted, the Live Intelligence Map remains completely static. If the Ollama local daemon is halted, its corresponding vortex in The Well drops to zero angular velocity immediately. Real user activity telemetry is strictly separated from synthetic benchmark executions. Telemetry is treated not as marketing decoration, but as an auditor-grade scientific instrument.

---

## 2. In-Memory Event Bus & Asynchronous Distribution Core

To support continuous telemetry frames without impacting the latency-critical inference path, the telemetry engine is decoupled from the synchronous execution pipeline via an asynchronous in-memory broadcast bus.

```
+--------------------------------------------------------------------------------------------------+
|                                    SETU-NETRA INFERENCE PIPELINE                                 |
|  [QueryAnalyzer] -> [AdaptiveRouter] -> [WorkerPool] -> [ModelAdapter] -> [CitationVerifier]   |
+--------------------------------------------------------------------------------------------------+
                                                    |
                                      (Non-blocking Thread Yield)
                                                    v
+--------------------------------------------------------------------------------------------------+
|                               ASYNC TELEMETRY EVENT BUS (SINGLE PROCESS)                         |
|   +------------------------------------------------------------------------------------------+   |
|   |                       Circular Ring Buffer (Capacity: 2048 Events)                       |   |
|   |  [Event 1001] -> [Event 1002] -> [Event 1003] -> ... -> [Event 1042]                     |   |
|   +------------------------------------------------------------------------------------------+   |
|                                                    |                                             |
|                    +-------------------------------+-------------------------------+             |
|                    v                               v                               v             |
|         [Client Queue 1 (SSE)]          [Client Queue 2 (SSE)]          [Historical DB Sink]     |
|         (Live Intelligence Map)              (The Well)                  (SQLite Append-Only)    |
|         Bounded: 256 frames max        Bounded: 256 frames max         Serialized WAL writes     |
+--------------------------------------------------------------------------------------------------+
```

### 2.1 Event Bus Design & Scope Constraints
1. **Single-Process Scope:** The initial in-memory `EventBus` operates within a single Python process. If the application is scaled across multiple Uvicorn worker processes in Hosted Public Mode, an external pub/sub broker (e.g., Redis or Dragonfly) becomes required to broadcast events across process boundaries.
2. **Correlation ID Tracking:** Every request is assigned a unique correlation ID (`corr_<uuid4>`) at API ingress. This ID is embedded in every emitted lifecycle event, enabling deterministic end-to-end trace reconstruction.
3. **Replay Capabilities via `Last-Event-ID`:** The circular ring buffer retains the most recent $N = 2048$ events. When a client reconnects following a network drop, the server reads the client's `Last-Event-ID` HTTP header and replays missed events before switching to live broadcast mode.
4. **Bounded Queues & Slow Client Handling:** Each connected SSE subscriber receives a dedicated queue bounded to $M = 256$ frames. If a slow consumer cannot process frames at delivery rate, the oldest unread frames are dropped and a `CLIENT_BACKPRESSURE_WARNING` packet is emitted. Inference worker threads are never blocked by slow network clients.
5. **Heartbeat Messages:** The server transmits `: ping\n\n` comments every 15 seconds over open SSE connections to prevent intermediate reverse proxies or client timeouts from dropping the connection.

### 2.2 Unified Request Lifecycle Event Schema
Every event traversing the bus conforms to the unified `TelemetryEvent` schema:

```json
{
  "event_id": 1042,
  "correlation_id": "corr_88f0c1a2-3b4c-4e5f-9a1b-2c3d4e5f6a7b",
  "query_id": "qry_88f0c1a2",
  "timestamp_ns": 1774353120145230000,
  "timestamp_iso": "2026-03-24T14:32:00.145Z",
  "event_type": "WORKER_SLOT_DISPATCHED",
  "source_subsystem": "InferenceWorkerPool",
  "payload": {
    "worker_id": "ollama/qwen3.5:2b_w1",
    "scheduler": "adaptive",
    "queue_depth_at_dispatch": 0,
    "allocated_threads": 4,
    "current_worker_rss_mb": 2450.5
  }
}
```

#### Deterministic Lifecycle States:
$$\begin{aligned}
\text{REQUEST\_INGRESS} &\longrightarrow \text{ANALYSIS\_COMPLETE} \longrightarrow \text{ROUTER\_DECISION} \longrightarrow \text{WORKER\_DISPATCH} \\
&\longrightarrow \text{RETRIEVAL\_PASSAGES} \longrightarrow \text{TOKEN\_STREAM\_BURST} \longrightarrow \text{VERIFIER\_TAXONOMY} \\
&\longrightarrow \text{EGRESS\_COMPLETED}
\end{aligned}$$

---

## 3. Mathematical Model of "The Well" (Capacity & Fluid Reservoir)

**The Well** translates physical systems engineering metrics into an organic fluid reservoir simulation. 

The state of the reservoir at time $t$ is a 5-tuple:
$$\mathcal{W}(t) = \langle D(t), A(t), \vec{\Omega}(t), S(t), \Theta(t) \rangle$$

```
+~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~+
| ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~  Surface Agitation A(t) ~ ~ ~ ~ ~ ~ ~ ~ ~ | <--- Inflow Rate \lambda(t)
|                                                                 |
|      / \               |  |                                     |
|     /   \   Vortex     |  |                                     |
|    ( ( ) )  \omega_1   |  |   Free Liquid Headroom D(t)         |
|     \   /              |  |   (Normalized Available RAM)        |
|      \ /               |  |                                     |
|                                                                 |
+=================================================================+
| : : : : : : : : Sediment Bed S(t) (Fragmented RAM/Dead Queue) : |
+-----------------------------------------------------------------+
```

### 3.1 Available RAM Headroom: Depth Transformation $D(t)$
* **Underlying Variable:** Available physical RAM headroom $M_{free}(t)$ in megabytes, sampled directly via Windows `kernel32.GlobalMemoryStatusEx` (`ullAvailPhys`).
* **Units:** Megabytes (MB).
* **Smoothing:** Exponential Moving Average (EMA) with half-life $t_{1/2} = 1.0\text{ s}$ ($\alpha_{ram} = 1 - e^{-\Delta t / 1.0}$):
  $$\bar{M}_{free}(t) = \alpha_{ram} M_{free}(t) + (1 - \alpha_{ram}) \bar{M}_{free}(t - \Delta t)$$
* **Normalization & Bounds:**
  Let $M_{total}$ be total installed physical RAM (e.g. 16,075 MB) and $M_{reserved} = 1,536\text{ MB}$ be the OS safety margin.
  $$D(t) = \min\left(1.0, \, \max\left(0.0, \, \frac{\bar{M}_{free}(t) - M_{reserved}}{M_{total} - M_{reserved}}\right)\right)$$
* **Behavior:** When RAM headroom is 8 GB, $D(t) \approx 0.44$. When Qwen 2B loads ($2.5\text{ GB}$), $D(t)$ visibly drops to $\approx 0.27$.

### 3.2 Request Arrival Rate: Surface Agitation $A(t)$
* **Underlying Variable:** Incoming request arrival rate $\lambda(t)$ measured over a sliding 10-second window:
  $$\lambda(t) = \frac{N_{\text{requests}}(t - 10\text{ s}, \, t)}{10.0} \quad \text{[Requests / Second (QPS)]}$$
* **Smoothing:** Damped harmonic oscillator modeling liquid surface waves:
  $$\frac{d^2 A}{dt^2} + 2\zeta\omega_0 \frac{dA}{dt} + \omega_0^2 A = \kappa \cdot \lambda(t)$$
  Where:
  * Damping ratio $\zeta = 0.50$ (critical damping preventing sustained resonance).
  * Natural frequency $\omega_0 = 2\pi \times 1.2\text{ rad/s}$.
  * Scaling factor $\kappa = 0.25$.
* **Bounds:** $A(t) \in [0.0, 1.0]$. When QPS is zero, $A(t) \to 0.0$ (calm, mirror surface). When bursts of queries arrive, dynamic concentric ripples propagate.

### 3.3 Worker Activity: Vortex Angular Velocity $\vec{\Omega}(t)$
* **Underlying Variable:** Token generation rate $\tau_w(t)$ for each active worker $w$:
  $$\tau_w(t) = \frac{\Delta \text{Tokens}_w}{\Delta t} \quad \text{[Tokens / Second]}$$
* **Normalization & Bounds:**
  Let $\tau_{rated}$ be the model's rated CPU generation speed (e.g., $20.0\text{ tok/s}$ for Qwen 2B, $50.0\text{ tok/s}$ for SmolLM2).
  The normalized worker load $\nu_w(t) \in [0.0, 1.0]$ is:
  $$\nu_w(t) = \min\left(1.0, \, \frac{\tau_w(t)}{\tau_{rated}}\right)$$
* **Angular Velocity Formulation:**
  $$\omega_w(t) = \omega_{max} \cdot \left(\nu_w(t)\right)^{1.2} \quad \text{[Radians / Second]}$$
  Where $\omega_{max} = 4\pi\text{ rad/s}$ ($2.0\text{ rev/s}$).
* **Vortex Funnel Depth:**
  $$h_w(t) = \frac{\omega_w(t)^2 \cdot R_{core}^2}{2g} \quad \text{clamped to } [0.0, 0.4 \cdot D(t)]$$
* **Visual Integrity Rule:** Progress indicators and vortex depths are rendered **only** when driven by real token stream events from the backend. The UI never displays synthetic percentage progressions.

### 3.4 Processing Capacity & Backpressure: Sediment Bed $S(t)$
* **Underlying Variables:**
  1. Active queue backlog $Q_{backlog}(t)$ in requests.
  2. Memory fragmentation / uncompacted SQLite WAL pages $W_{pages}(t)$.
* **Normalization & Bounds:**
  $$S(t) = \min\left(0.40, \, 0.25 \cdot \frac{Q_{backlog}(t)}{Q_{max}} + 0.15 \cdot \frac{W_{pages}(t)}{W_{threshold}}\right)$$
* **Behavior:** Under heavy queue congestion or database write contention, dark silt accumulates at the reservoir bed.

### 3.5 Thermal & Pressure State: Chromatic Tint $\Theta(t)$
* **Underlying Variable:** CPU utilization $U_{cpu}(t) \in [0.0, 1.0]$ sampled via `kernel32.GetSystemTimes`.
* **Smoothing:** EMA with half-life $2.0\text{ s}$.
* **Chromatic Mapping:**
  $$\text{Palette}(\Theta) = \begin{cases} 
  \text{Archival River Teal } (\#1C3D3D) & \text{if } \bar{U}_{cpu}(t) < 0.40 \\
  \text{Warm Ochre } (\#C27D38) & \text{if } 0.40 \le \bar{U}_{cpu}(t) < 0.75 \\
  \text{Deep Crimson Alert } (\#8B2635) & \text{if } \bar{U}_{cpu}(t) \ge 0.75 \quad (\text{Thermal Throttling})
  \end{cases}$$

---

## 4. Observability Statistics & Scientific Evaluation

### 4.1 Wilson Score Confidence Intervals (Binary Proportions Only)
* **Statistical Scope:** Wilson score intervals are applied **strictly to appropriately sampled binary proportions** (e.g., whether an individual query answer is `EVIDENCE_BACKED` vs. not, or retrieval hit@3 success vs. failure).
* **Strict Labeling Rule:** These intervals represent **statistical sampling uncertainty of empirical measurements** across a sample of $n$ queries. They must **NEVER be labeled as "AI model confidence"**.
* **Formula:**
  For a sample of $n$ independent trials with $k$ positive outcomes ($\hat{p} = k/n$):
  $$CI_{95\%} = \frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$
  Where $z = 1.95996$.
* **Reporting Standard:** Every reported interval must explicitly display sample size $n$ and denominator:
  $$\text{Evidence Grounding Rate: } 86.0\% \quad [95\% \text{ CI: } 77.8\% - 91.5\%, \,\, n=100, \,\, \text{trials}=100]$$

### 4.2 Latency Percentiles via Exact Sliding Buffers
Latency measurements (dense retrieval, model inference, citation verification) are stored in an exact ring buffer of the last 1,000 requests. P50, P90, and P99 are calculated using standard quantile estimation (Hyndman-Fan Type 7).

### 4.3 Separation of Real User Telemetry vs. Synthetic Benchmarks
* Real user queries (originating from `/api/v1/query`) and synthetic automated benchmark runs (from `benchmarks/`) are tagged with distinct `data_source` metadata (`real_user` vs. `synthetic_benchmark`).
* The Faculty Observer Deck and Live Intelligence Map maintain separate query streams to ensure synthetic load tests never contaminate operational user performance records.
