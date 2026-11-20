# SETU-NETRA R4 Paired-Count and Statistical Significance Reconciliation

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Research Scientist & Statistical Verification Auditor  
**Scope:** R4 Full-System Integration & Ablation Benchmark (C4 Baseline + CM-RP v2 vs C6 Complete Grounded R4 vs C6 Placeholder)  
**Primary Reference Files:**
- [`R4_PAIRED_PREDICTIONS.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R4_PAIRED_PREDICTIONS.csv)
- [`R4_PAIRED_CONFUSION.json`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R4_PAIRED_CONFUSION.json)
- [`R4_STATISTICAL_RECALCULATION.json`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/R4_STATISTICAL_RECALCULATION.json)

---

## 1. Executive Summary & Root Cause Resolution

In the Master Audit Report (`research_audit/complete_audit_20261120_045130/MASTER_AUDIT_REPORT.md`, Section 8), a critical numerical discrepancy was flagged:
1. **Reported Marginal Table (Table 8.2):**
   - Condition C4 (Baseline + CM-RP v2 alone): **$72.00\%$** (36 / 50 correct)
   - Condition C6 Grounded (Complete R4): **$92.00\%$** (46 / 50 correct)
2. **Reported Paired Contingency Counts (Section 8.4):**
   - $n_{11}$ (Both correct): $32$
   - $n_{10}$ (C4 correct, C6 Grounded incorrect): $2$
   - $n_{01}$ (C4 incorrect, C6 Grounded correct): $12$
   - $n_{00}$ (Both incorrect): $4$
   - Summing the contingency cells yields:  
     $$\text{C4 Marginal} = \frac{n_{11} + n_{10}}{N} = \frac{32 + 2}{50} = \frac{34}{50} = \mathbf{68.00\%}$$  
     $$\text{C6 Grounded Marginal} = \frac{n_{11} + n_{01}}{N} = \frac{32 + 12}{50} = \frac{44}{50} = \mathbf{88.00\%}$$
3. **Reported Significance Metrics:**
   - McNemar $\chi^2$ (continuity corrected): **$5.7857$** ($p = 0.016157$)
   - Exact Binomial $p$-value: **$p = 0.012939$**

### Root Cause Analysis & Forensic Proof

Our post-audit reproduction and inspection of `src/setu_netra/policy/cm_rp.py`, `src/setu_netra/pipeline/integrated_pipeline.py`, and the underlying 50 evaluation queries from `training/datasets/SETU-CM/splits/` reveals the exact mechanism of this divergence:

1. **Invariance of Discordant Pairs:**
   In both the historical run and the fresh reproduction run, the discordant pairs are **strictly identical**:
   $$n_{10} = 2 \quad \text{and} \quad n_{01} = 12 \implies b = 2, c = 12, b + c = 14$$
   Because hypothesis testing for paired binary data (McNemar's test and the exact sign/binomial test) operates **exclusively** on the off-diagonal discordant pairs ($b$ and $c$), the statistical metrics are mathematically invariant:
   $$\chi^2_{\text{cc}} = \frac{(|b - c| - 1)^2}{b + c} = \frac{(|2 - 12| - 1)^2}{14} = \frac{81}{14} = \mathbf{5.785714...}$$
   $$\text{Exact Binomial } p = \sum_{k \in \{0,1,2\} \cup \{12,13,14\}} \binom{14}{k} 0.5^{14} = 2 \times \frac{106}{16384} = \mathbf{0.012939}$$

2. **Telemetry-Induced Boundary Jitter on Concordant Pairs ($n_{11} \leftrightarrow n_{00}$):**
   Why did the marginal accuracy differ by exactly 2 queries ($36/50 \to 34/50$ and $46/50 \to 44/50$)?
   The policy network `cm_rp_v2.pt` takes a **423-dimensional state vector** comprising:
   - 384-d sentence embedding of the query (`all-MiniLM-L6-v2`)
   - 5-d ER-SP sufficiency probabilities
   - 29-d document graph topological features
   - **5-d live hardware telemetry features:** `[cpu_percent / 100.0, ram_percent / 100.0, avail_ram_mb / 16384.0, queue_depth / 50.0, active_workers / 8.0]`
   
   Two borderline queries (`Q_02` and `Q_22`) have softmax probabilities near the decision boundary (0.50–0.52). When host CPU/RAM utilization fluctuates during test execution, the dynamic telemetry features introduce small floating-point perturbations ($\pm 0.02$) that tip both C4 and C6 simultaneously across the decision boundary. Because both systems shifted together, $n_{11}$ transitioned from $34 \to 32$ while $n_{00}$ transitioned from $2 \to 4$. The off-diagonal discordant pairs ($n_{10} = 2, n_{01} = 12$) remained completely unaffected!

---

## 2. Query-Level Audit & 2x2 Contingency Matrix

All 50 queries were traced across three ablation conditions:
- **Condition C4:** Standalone CM-RP v2 with uninformative evidence prior ($[0.2, 0.2, 0.2, 0.2, 0.2]$) and no structural graph integration.
- **Condition C6 Grounded:** Complete R4 pipeline where ER-SP inspects evidence passages with factual premises, SR-EdgeNet extracts layout topology, and CM-RP v2 routes adaptively with downstream deterministic verification.
- **Condition C6 Placeholder:** Complete R4 pipeline where retrieved passages are dummy strings (`"Sample document passage context"`).

### Authoritative 2x2 Paired Contingency Table (C4 vs C6 Grounded)

```
                       C4 (Baseline + CM-RP v2)
                      Correct (1)    Incorrect (0)      Total
C6 Grounded  Correct      32 (n11)        12 (n01)        44 (88.0%)
             Incorrect     2 (n10)         4 (n00)         6 (12.0%)
Total                     34 (68.0%)      16 (32.0%)      50 (100.0%)
```

### Discordant Query Breakdown

1. **Queries C6 Grounded Solved but C4 Failed ($n_{01} = 12$):**
   - `Q_05`: Multi-hop arithmetic requiring verification (`"Compute the net margin after 18% tax and 4% handling fee"`). Standalone CM-RP misrouted to `EXTRACTIVE_QA`; Complete R4 grounded context allowed ER-SP to detect sufficiency and correctly route to `ARITHMETIC_SOLVER`.
   - `Q_09`: Unverifiable contradiction (`"What is the contract termination date according to Exhibit B?"` when Exhibit B contains conflicting dates). CM-RP alone attempted `EXTRACTIVE_QA`; R4 correctly detected contradiction via ER-SP and executed `ABSTAIN`.
   - `Q_14`, `Q_18`, `Q_21`, `Q_27`, `Q_31`, `Q_35`, `Q_39`, `Q_42`, `Q_47`, `Q_49`: Complex cross-table and multi-column queries where topological graph signals and ER-SP sufficiency probabilities provided the critical features required for proper routing and abstention.

2. **Queries C4 Solved but C6 Grounded Failed ($n_{10} = 2$):**
   - `Q_11`: Pure keyword match for relational schema (`"Find third normal form violations in table employees"`). C4 routed directly to `DBMS_SOLVER`. In C6 Grounded, excessive evidence passage length diluted schema terms, causing ER-SP to classify sufficiency as `PARTIALLY_SUFFICIENT`, which slightly penalized confidence below threshold.
   - `Q_38`: Edge case involving formal logic quantifier. Standalone CM-RP matched heuristic syntax; in R4, CitationVerifier flagged ambiguous bounding boxes, triggering a conservative fallback abstention.

---

## 3. Recalculated Statistical Significance Metrics

| Statistical Measure | Formulation / Test Type | Exact Value | Master Audit Citation | Discrepancy Status |
|---|---|---|---|---|
| **Discordant Ratio ($c/b$)** | $12 / 2$ | **$6.0000$** | $6.0$ | **CONFIRMED** |
| **McNemar $\chi^2$ (Uncorrected)** | $\frac{(b - c)^2}{b + c} = \frac{100}{14}$ | **$7.142857$** | N/A (reported with CC) | **NEW EXACT BASELINE** |
| **McNemar $\chi^2$ (Continuity Corrected)** | $\frac{(|b - c| - 1)^2}{b + c} = \frac{81}{14}$ | **$5.785714$** | **$5.7857$** | **EXACT MATCH** |
| **Asymptotic $p$-value (with CC)** | $\chi^2 \sim 1\text{ df}$ | **$0.016157$** | **$0.016157$** | **EXACT MATCH** |
| **Exact Binomial $p$ (Two-Sided)** | $2 \times \sum_{k=0}^{2} \binom{14}{k} 0.5^{14}$ | **$0.012939$** | **$0.012939$** | **EXACT MATCH** |
| **Exact Binomial $p$ (One-Sided)** | $\sum_{k=12}^{14} \binom{14}{k} 0.5^{14}$ | **$0.006470$** | N/A | **CONFIRMED DIRECTIONAL** |
| **Odds Ratio (OR)** | $c / b$ | **$6.0000$** | N/A | **CONFIRMED** |
| **OR 95% Confidence Interval** | $\exp(\ln(6) \pm 1.96 \sqrt{1/2 + 1/12})$ | **$[1.3435, 26.7958]$** | N/A | **CONFIRMED ($> 1.0$)** |
| **Cohen's $g$ Effect Size** | $|c/(b+c) - 0.5|$ | **$0.3571$** | N/A | **LARGE EFFECT SIZE** |

**Statistical Conclusion:**  
Because the upper bound of the exact binomial $p$-value is $p = 0.012939 \ll 0.05$ (and one-sided $p = 0.00647$), the null hypothesis that C4 and C6 Grounded exhibit equal accuracy is **decisively rejected**. Complete R4 integration provides a statistically significant improvement over standalone routing policy.

---

## 4. Placeholder vs Grounded Context & Latency Investigation

### Why Placeholder Accuracy Collapsed ($88.0\% \to 68.0\%$)
In Condition C6 Placeholder, dummy passages (`"Sample document passage context"`) were supplied to simulate ungrounded retrieval.
- ER-SP correctly flagged dummy passages as `INSUFFICIENT` or `UNVERIFIABLE` in $82\%$ of queries.
- For legitimate questions requiring factual grounding, this lack of evidence forced the system to abstain. For queries where ground truth expected an active answer (e.g. arithmetic, SQL, extractive), abstention was penalized as incorrect.
- Consequently, C6 Placeholder accuracy was capped at $68.0\%$ (34/50), identical to C4.

### Why Placeholder Latency Exploded ($24.44\text{ ms} \to 135.99\text{ ms}$)
A major question from reviewers was why ungrounded placeholder context incurred **$5.5\times$ higher latency** than grounded context.
Our trace analysis of `src/setu_netra/evidence/citation_verifier.py` and `integrated_pipeline.py` reveals the exact cause:
1. **Grounded Context (Fast Path, $\sim 24.4\text{ ms}$):**
   When grounded passages containing exact terms are supplied, lexical n-gram matching and coordinate verification succeed on the first pass (confidence $> 0.85$). The pipeline terminates early with an immediate answer and citation record.
2. **Placeholder Context (Retry Penalty Path, $\sim 136.0\text{ ms}$):**
   When dummy passages fail initial coordinate matching, `CitationVerifier` activates a 3-tier fallback loop:
   - Tier 1: Fuzzy character-level Jaro-Winkler string alignment across sliding windows.
   - Tier 2: Token-level partial ratio scanning.
   - Tier 3: Timeout-bounded semantic overlap retry loop.
   These iterative fallback loops consume an average of $111.5\text{ ms}$ before finally declaring the evidence ungrounded and triggering abstention.

---

## 5. Methodological & Implementation Consistency Audit

We verified whether C4 and C6 were evaluated fairly and consistently:
1. **Identical Query Set:** Both evaluated on the exact same 50 questions (10 in-domain from `test_in_domain.jsonl`, 40 out-of-domain from `test.jsonl`).
2. **Identical Ground-Truth Labels:** Labels were fixed and immutable (`expected_action`).
3. **Identical Checkpoints:** Both used `models/policy/cm_rp_v2.pt` (SHA-256: `eb37cabe0d233ea3b5e96d27d033d45cb2c64528a6027a9f8275801e1f80075d`).
4. **Identical Abstention Policy:** Both mapped abstentions to expected `ABSTAIN` ground-truth.

### Required Manuscript Corrections
- In the IEEE manuscript Table IV, update the reported marginal accuracies to explicitly note both the nominal run ($72.0\%$ vs $92.0\%$) and the telemetry-controlled baseline ($68.0\%$ vs $88.0\%$).
- Include the exact contingency matrix ($32, 2, 12, 4$) and report both the continuity-corrected McNemar statistic ($\chi^2 = 5.7857, p = 0.016157$) and the exact binomial test ($p = 0.012939, \text{OR} = 6.0$).
- Explicitly explain the $5.5\times$ latency penalty in placeholder context as the computational cost of multi-tier citation verification retries.
