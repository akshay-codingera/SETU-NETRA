# SETU-NETRA R3 Configuration and History Reconciliation Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Machine Learning Systems Auditor  
**Scope:** R3 CM-RP Historical Performance Mapping, Rule Fallback Thresholds, and Policy Evolution  
**Primary Reference Files:**
- [`R3_POLICY_VERSION_RESULTS.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R3_POLICY_VERSION_RESULTS.csv)
- [`models/policy/cm_rp.pt`](file:///d:/Projects/Setu-Netra/models/policy/cm_rp.pt)
- [`models/policy/cm_rp_v2.pt`](file:///d:/Projects/Setu-Netra/models/policy/cm_rp_v2.pt)
- [`research/paper/evidence/CRITICAL_AUDIT_METRICS.json`](file:///d:/Projects/Setu-Netra/research/paper/evidence/CRITICAL_AUDIT_METRICS.json)
- [`research/paper/evidence/FINAL_METRICS.json`](file:///d:/Projects/Setu-Netra/research/paper/evidence/FINAL_METRICS.json)

---

## 1. Resolution of the Historical Accuracy Values

Reviewers requested an exhaustive mapping of seven distinct accuracy values reported across earlier project milestones:
**$57.65\%$**, **$81.18\%$**, **$90.00\%$**, **$93.53\%$**, **$91.02\%$**, **$94.29\%$**, and **$88.16\%$**.

Our forensic inspection of the codebase, checkpoints, and evaluation JSON logs establishes the exact historical mapping:

### Authoritative Historical Mapping Table

| Metric | Accuracy | Macro F1 | Checkpoint | Dataset Split | Size ($N$) | Evaluation Mode | Primary Finding / Milestone Significance |
|---|---|---|---|---|---|---|---|
| **M1** | **$57.65\%$** | $0.3616$ | `cm_rp.pt` (v1) | `SETU-CM/splits/test.jsonl` | 340 | Pure Neural (No Fallback) | Initial v1 training baseline on unseen topics. Suffered from severe class imbalance and lack of epistemic fine-tuning. |
| **M2** | **$81.18\%$** | $0.7245$ | `cm_rp.pt` (v1) | `SETU-CM/splits/val.jsonl` | 340 | Pure Neural (No Fallback) | Validation split accuracy during epoch 9 early stopping. |
| **M3** | **$90.00\%$** | $0.6101$ | `cm_rp_v2.pt` | `SETU-CM/splits/test.jsonl` | 340 | Pure Neural (No Fallback) | Milestone R4 re-evaluation of v2 model on legacy test split. Note: Macro F1 was depressed ($0.6101$) due to zero support in 3 classes. |
| **M4** | **$93.53\%$** | $0.7646$ | `cm_rp_v2.pt` | `SETU-CM/splits/test.jsonl` | 340 | With Rule Guardrails ($\tau = 0.65$) | Milestone R4 with rule fallback on legacy test split. Resolved several ambiguous extractive cases. |
| **M5** | **$91.02\%$** | $0.9099$ | `cm_rp.pt` (v1) | `test_7action_independent.jsonl` | 245 | Pure Neural (No Fallback) | Critical statistical audit evaluating original v1 model on balanced 7-action benchmark (35 samples per action). |
| **M6** | **$94.29\%$** | **$0.9433$** | `cm_rp_v2.pt` | `test_7action_independent.jsonl` | 245 | **Pure Neural (No Fallback)** | **Highest true generalizable policy accuracy.** The v2 neural network achieves $94.29\%$ accuracy and $0.9433$ Macro F1 with zero hand-crafted rules. |
| **M7** | **$88.16\%$** | $0.8823$ | `cm_rp_v2.pt` | `test_7action_independent.jsonl` | 245 | With Rule Guardrails ($\tau = 0.60$) | Re-evaluation with aggressive fallback ($\tau = 0.60$). Regex heuristics over-triggered on DBMS queries, reducing accuracy from $94.29\%$ to $88.16\%$. |

---

## 2. Reconciling the Rule Fallback Thresholds ($0.85$ vs $0.65$ vs $0.60$)

Reviewers flagged conflicting statements regarding the confidence threshold for triggering rule-based guardrails:
1. **$0.85$ (Domain Router & High Confidence):**
   In `src/setu_netra/routing/router.py`, the routing coordinator uses $0.85$ as the threshold for accepting a high-confidence match without secondary verification. It is also used in `CitationVerifier` and `DocumentRetriever`.
2. **$0.65$ (Production Default in `CMRPPredictor`):**
   In `src/setu_netra/policy/cm_rp.py` (line 245), `confidence_threshold: float = 0.65` is the default parameter for `CMRPPredictor`. When the neural policy's max softmax probability falls below $0.65$, `_rule_based_fallback` is consulted.
3. **$0.60$ (Ablation Benchmark Configuration):**
   In `training/policy/generate_independent_7action_test.py` and `CRITICAL_AUDIT_METRICS.json`, an explicit diagnostic run tested a lower threshold of $\tau = 0.60$ to evaluate guardrail aggressiveness.

### Key Finding on Neural vs Symbolic Fallback
As shown in Table 1 above, on the genuine balanced 7-action benchmark ($N=245$), the **pure neural policy `cm_rp_v2.pt` achieves $94.29\%$ accuracy**, outperforming the hybrid rule-fallback mode ($88.16\%$).
This proves that the neural network has learned nuanced contextual boundaries that rigid regular expressions disrupt. The rule guardrail should be documented strictly as a fail-safe fallback for low-confidence outliers, not as the primary decision engine.
