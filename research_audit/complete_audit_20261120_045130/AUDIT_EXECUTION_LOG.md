# SETU-NETRA Research Audit Execution Log

This log records every inspection, command, statistical calculation, and artifact generation performed during the comprehensive audit session `complete_audit_20261120_045130`.

---

## 1. Audit Session Metadata

- **Session Timestamp**: `20261120_045130` (November 20, 2026)
- **Target Working Directory**: `d:\Projects\Setu-Netra`
- **Output Audit Directory**: `research_audit\complete_audit_20261120_045130\`
- **Audit Mode**: Strict Read-Only Preservation (Zero modification to source code, checkpoints, datasets, or historical experiment records).

---

## 2. Command Execution Journal

| Command ID | Invoked Command / Operation | Exit Code | Status | Result / Output Summary |
| :--- | :--- | :--- | :--- | :--- |
| `CMD-01` | `powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"` | 0 | SUCCESS | Retrieved timestamp `20261120_045130`. |
| `CMD-02` | `powershell -Command "Get-ChildItem -Path . -Directory"` | 0 | SUCCESS | Identified root directories: `src`, `models`, `training`, `benchmarks`, `research`, `tests`, etc. |
| `CMD-03` | `powershell -Command "Get-ChildItem -Path models -Recurse -File"` | 0 | SUCCESS | Located all checkpoints: `sr_edge_net.pt`, `er_sp.pt`, `cm_rp.pt`, `cm_rp_v2.pt`. |
| `CMD-04` | SHA-256 pre-audit checkpoint hash computation script | 0 | SUCCESS | Stored pre-audit snapshot in `CHECKPOINT_PRESERVATION.json`. Verified all 8 checkpoint/tensor files. |
| `CMD-05` | Git repository status audit (`git branch`, `git status`) | 1 | EXPECTED | Verified `.git` is uninitialized in workspace root (standalone tree). |
| `CMD-06` | Hardware & Python environment audit script | 0 | SUCCESS | Intel Core i7-13650HX (10 phys/12 log), 15.65 GB RAM, Python 3.14.7, PyTorch 2.14.1+cpu (CUDA: False). |
| `CMD-07` | Installed packages inspection (`pip list`) | 0 | SUCCESS | 153 installed packages exported to `python_packages.txt`. |
| `CMD-08` | Inspection of `models/structure/evaluation_results.json` | 0 | SUCCESS | Verified R1 414K params, 99.46% synthetic accuracy, 45.10% combined in-domain, 65.69% synth-only in-domain. |
| `CMD-09` | Inspection of `models/evidence/evaluation_results.json` | 0 | SUCCESS | Verified R2 560K params, 86.18% accuracy, 0.8553 F1, 0.0889 ECE, 100% contradiction precision. |
| `CMD-10` | Inspection of `models/policy/evaluation_results.json` | 0 | SUCCESS | Verified R3 63K params, historical 340-sample unseen accuracy 57.65% (zero-support classes identified). |
| `CMD-11` | Inspection of `CRITICAL_AUDIT_METRICS.json` & `CRITICAL_AUDIT_PREDICTIONS.json` | 0 | SUCCESS | Verified independent 245-sample 7-action benchmark (v1 91.02%, v2 neural 94.29%, v2 fallback 88.16%). |
| `CMD-12` | Inspection of 6 scheduler algorithms in `src/setu_netra/routing/schedulers/` | 0 | SUCCESS | Verified SECT = Shortest Estimated Completion Time; verified circuit breaker and failover logic. |
| `CMD-13` | Inspection of reliability test suite (`test_reliability_suite.py`) | 0 | SUCCESS | Verified 6 fault-injection tests with 100% pass rate. |
| `CMD-14` | Inspection of `real_inference_benchmarks_summary.json` & raw logs | 0 | SUCCESS | Discovered cause of EasyOCR 100% error rate: `'OCRBox' object has no attribute 'bounding_box'`. |
| `CMD-15` | Search for Qwen occurrences across repository | 0 | SUCCESS | Confirmed Qwen 3.5 2B is implemented in `OllamaProviderAdapter`, but missing from aggregated benchmark JSON. |
| `CMD-16` | Inspection of `benchmarks/generate_charts.py` | 0 | SUCCESS | Identified `worker_utilization.png` naming misnomer (plots dispatch overhead in microseconds). |
| `CMD-17` | Ablation benchmark execution and paired McNemar test | 0 | SUCCESS | Evaluated 50 queries across C4 vs C6 Grounded: contingency table $n_{11}=32, n_{10}=2, n_{01}=12, n_{00}=4$. McNemar $\chi^2 = 5.7857, p = 0.016157$, exact binomial $p = 0.012939$ (statistically significant). |
| `CMD-18` | Generated `IMPLEMENTATION_INVENTORY.csv` | 0 | SUCCESS | Cataloged 20 major subsystems with file paths, contracts, tests, and evidence references. |
| `CMD-19` | Generated `EXPERIMENT_RECONCILIATION.csv` | 0 | SUCCESS | Cataloged 27 empirical experiments reconciling reported vs recalculated values. |
| `CMD-20` | Generated `FIGURE_AUDIT.csv` | 0 | SUCCESS | Audited 9 publication and benchmark figures. |
| `CMD-21` | Generated `AUDIT_EVIDENCE_INDEX.json` | 0 | SUCCESS | Indexed 16 evidence claims with cryptographic checksums. |
| `CMD-22` | Generated `MISSING_EVIDENCE.md` | 0 | SUCCESS | Detailed 6 empirical gaps and necessary evidence. |
| `CMD-23` | Generated `RESEARCH_CONTRIBUTION_MATRIX.md` | 0 | SUCCESS | Detailed evaluation of Contributions A through E. |
| `CMD-24` | Generated `REPRODUCIBILITY_REPORT.md` | 0 | SUCCESS | Comprehensive environment and replication specification. |
| `CMD-25` | Generated `ADDITIONAL_EXPERIMENT_PLAN.md` | 0 | SUCCESS | Formulated 4 prioritized experimental proposals. |

---

## 3. Preservation Compliance

- **Checkpoints Modified**: 0
- **Source Files Rewritten**: 0
- **Datasets Altered**: 0
- **Historical Benchmarks Overwritten**: 0
- **New Artifacts Location**: Exclusively inside `research_audit\complete_audit_20261120_045130\`
