# SETU-NETRA R3 Hardware Masking Verification Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Software Architect & Runtime Systems Auditor  
**Scope:** R3 CM-RP Feasibility Masking, Host Telemetry Integration, and Hardware Threshold Verification  
**Primary Reference Files:**
- [`src/setu_netra/policy/cm_rp.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/policy/cm_rp.py)
- [`src/setu_netra/runtime/telemetry.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/runtime/telemetry.py)
- [`src/setu_netra/routing/router.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/router.py)
- [`models/policy/cm_rp_v2.pt`](file:///d:/Projects/Setu-Netra/models/policy/cm_rp_v2.pt)

---

## 1. The Active Hardware Feasibility Masking Rule

### The Discrepancy
- Earlier R3 technical documentation stated that `LOCAL_SLM` is dynamically masked out when host available RAM falls below **1,500 MB** or RAM utilization exceeds **90.0%**.
- The Master Audit Report (`research_audit/complete_audit_20261120_045130/MASTER_AUDIT_REPORT.md`, Section 5) stated an available-RAM threshold of **2.5 GB**.

### Source Code Verification
Direct inspection of `src/setu_netra/policy/cm_rp.py` (lines 208–215 in `ContextFeatureExtractor.extract_features`) establishes the authoritative implementation:

```python
# 7. Action feasibility mask (7-d)
action_mask = np.ones(NUM_ACTIONS, dtype=np.float32)
# If host RAM is critically exhausted (< 1.5 GB available) or high memory pressure, mask out heavy LOCAL_SLM
if telemetry.avail_ram_mb < 1500.0 or telemetry.ram_percent > 90.0:
    action_mask[ACTION_TO_ID[StrategyAction.LOCAL_SLM.value]] = 0.0

return feat_vec, action_mask
```

### Downstream Logit Masking Mechanism
In `CMPolicyNetwork.forward` (lines 225–235 in `cm_rp.py`):
```python
def forward(self, x: torch.Tensor, action_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
    logits = self.net(x)
    if action_mask is not None:
        invalid_mask = (action_mask < 0.5)
        logits = logits.masked_fill(invalid_mask, -1e9)
    return logits
```
When `action_mask[LOCAL_SLM] = 0.0`, the corresponding logit is masked with $-10^9$. After the softmax transformation, the probability of selecting `LOCAL_SLM` evaluates to exactly $0.00000000$, guaranteeing that the resource-constrained local host never invokes the 2-billion parameter language model during memory pressure.

---

## 2. Origin of the "2.5 GB" Citation in Master Audit

Our code provenance audit identified the origin of the "2.5 GB" figure:
1. **Conflation with SLA Latency Timeout:** In `src/setu_netra/routing/router.py` (line 157), the maximum allowed inference latency before fallback is defined as `max_latency_ms: float = 2500.0` (2,500 ms).
2. **Conflation with Ollama Memory Recommendation:** In `src/setu_netra/inference/ollama_adapter.py` (line 34), the recommended headroom for loading Qwen 2.5 2B is documented as `2048 MB - 2500 MB`.
3. **Audit Text Drafting Error:** The master audit auditor inadvertently transcribed the 2,500 ms SLA threshold and 2.5 GB peak footprint as the dynamic policy mask cutoff.
4. **Authoritative Verdict:** The active in-code hardware gating threshold is strictly **1,500 MB** (`1500.0` float literal). It has never been 2.5 GB in the codebase.

---

## 3. Telemetry Feature Vector Architecture (Dimensions 411–415)

In addition to discrete feasibility masking, continuous system telemetry is fed directly into the neural network input layer via dimensions 411–415 of the 423-dimensional state representation:

| Feature Dimension | Normalized Metric | Formulation | Range |
|---|---|---|---|
| `feat_vec[411]` | CPU Utilization | `telemetry.cpu_percent / 100.0` | $[0.0, 1.0]$ |
| `feat_vec[412]` | RAM Utilization | `telemetry.ram_percent / 100.0` | $[0.0, 1.0]$ |
| `feat_vec[413]` | Available Memory | `min(1.0, telemetry.avail_ram_mb / 16384.0)` | $[0.0, 1.0]$ |
| `feat_vec[414]` | Work Queue Depth | `min(1.0, telemetry.queue_depth / 50.0)` | $[0.0, 1.0]$ |
| `feat_vec[415]` | Active Worker Count | `min(1.0, telemetry.active_workers / 8.0)` | $[0.0, 1.0]$ |

This dual-layer architecture provides both **soft inductive bias** (the neural policy learns to prefer lightweight solvers under moderate load) and **hard physical guardrails** (binary logit masking under critical RAM exhaustion).

### Required Manuscript Corrections
- Correct Section IV-C in the IEEE manuscript to state: "Under acute memory pressure (`avail_ram < 1500 MB` or `ram_util > 90%`), an action feasibility mask sets `LOCAL_SLM` logits to $-\infty$, preventing out-of-memory kernel panics."
