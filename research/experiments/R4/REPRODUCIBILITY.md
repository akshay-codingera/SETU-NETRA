# SETU-NETRA: Milestone R4 Reproducibility Guide
**Complete Execution Protocols, Deterministic Seeds, and CLI Reproduction Commands**
*Milestone: R4 Final | Project: SETU-NETRA*

---

## 1. System Requirements & Environment

### Hardware Profile:
- **Architecture:** x86_64 CPU (Execution is CPU-first; no discrete GPU required)
- **Host Physical RAM:** Minimum 8 GB; Recommended 16 GB (System peak process footprint is ~605 MB)
- **Disk Storage:** Minimum 2 GB free disk space

### Software & Python Runtime:
- **Operating System:** Windows 10/11 or Linux (Ubuntu 20.04+)
- **Python Version:** Python 3.10+ (Verified on Python 3.14.7)
- **Core Dependencies:**
  - `torch >= 2.0.0`
  - `numpy >= 1.24.0`
  - `scikit-learn >= 1.2.0`
  - `sentence-transformers >= 2.2.0`
  - `pytest >= 7.0.0`
  - `pyyaml >= 6.0`
  - `pillow >= 9.0.0`

---

## 2. Pre-Flight Checkpoint & Dataset Verification

Verify that all required datasets and trained model weights are in place:

```powershell
# 1. Verify Checkpoints
Get-Item models/structure/sr_edge_net.pt
Get-Item models/evidence/er_sp.pt
Get-Item models/policy/cm_rp.pt
Get-Item models/policy/cm_rp_v2.pt

# 2. Verify Datasets
Get-Item training/datasets/SETU-SR/splits/test_synthetic.jsonl
Get-Item training/datasets/SETU-SR/splits/test_in_domain.jsonl
Get-Item training/datasets/SETU-ER/splits/test.jsonl
Get-Item training/datasets/SETU-CM/splits/test.jsonl

# 3. Verify Precomputed Embedding Caches
Get-Item training/structure/embedding_cache.pt
Get-Item training/evidence/embedding_cache.pt
```

---

## 3. Step-by-Step CLI Execution Instructions

### Step 3.1: Reproduce SR-EdgeNet (R1) Training & Evaluation
To retrain SR-EdgeNet from scratch using seed 42:
```powershell
.\.venv\Scripts\python.exe training/structure/train.py --config training/structure/config.yaml
```
To evaluate SR-EdgeNet on synthetic and in-domain test splits:
```powershell
.\.venv\Scripts\python.exe training/structure/evaluate.py
```

### Step 3.2: Reproduce ER-SP (R2) Training & Evaluation
To retrain ER-SP from scratch using seed 42:
```powershell
.\.venv\Scripts\python.exe training/evidence/train.py --config training/evidence/config.yaml
```
To evaluate ER-SP on held-out unseen topics and evaluate calibration error (ECE):
```powershell
.\.venv\Scripts\python.exe training/evidence/evaluate.py
```

### Step 3.3: Reproduce CM-RP v2 (R3 / R4) Training & Evaluation
To train the generalized CM-RP v2 policy checkpoint (`models/policy/cm_rp_v2.pt`):
```powershell
.\.venv\Scripts\python.exe training/policy/train_v2.py
```
To evaluate CM-RP v2 against the original v1 baseline and rule fallbacks:
```powershell
.\.venv\Scripts\python.exe training/policy/evaluate.py
```

---

## 4. End-to-End System Benchmarking (R4 Benchmark Suite)

To execute the complete Milestone R4 benchmark suite, compute all 3 empirical confusion matrices, execute the 6-configuration ablation study, measure hardware utilization, and generate `FINAL_METRICS.json`:

```powershell
.\.venv\Scripts\python.exe training/benchmarks/benchmark_e2e.py
```

Expected Output:
```
===========================================================================
SETU-NETRA: Milestone R4 End-to-End Benchmark & Verification Suite
===========================================================================
--- 1. Evaluating SR-EdgeNet (R1) Confusion Matrix ---
SR-EdgeNet Synthetic Test (N=4423): Acc: 99.46%, Macro F1: 0.9909
SR-EdgeNet In-Domain Test (N=204): Acc: 45.1%, Macro F1: 0.3434

--- 2. Evaluating ER-SP (R2) Confusion Matrix ---
ER-SP Unseen Test (N=340): Acc: 86.18%, Macro F1: 0.8553

--- 3. Evaluating CM-RP (R3) Confusion Matrix ---
CM-RP v2 Neural Unassisted (N=340): Acc: 90.0%, Macro F1: 0.6101
CM-RP v2 With Rule Fallback (N=340): Acc: 93.53%, Macro F1: 0.7646

===========================================================================
EXECUTING ABLATION STUDY (6 Controlled Configurations)
===========================================================================
  [C1_Baseline_Heuristic       ] Acc: 44.00% | Abstain F1: 0.0000 | Grounding: 0.608
  [C2_Baseline_Plus_SREdgeNet  ] Acc: 42.00% | Abstain F1: 0.0000 | Grounding: 0.594
  [C3_Baseline_Plus_ERSP       ] Acc: 24.00% | Abstain F1: 0.0000 | Grounding: 0.468
  [C4_Baseline_Plus_CMRP       ] Acc: 72.00% | Abstain F1: 0.5517 | Grounding: 0.932
  [C5_SREdgeNet_Plus_ERSP      ] Acc: 44.00% | Abstain F1: 0.0000 | Grounding: 0.608
  [C6_Complete_SETUNETRA_R4    ] Acc: 70.00% | Abstain F1: 0.5333 | Grounding: 0.930

FINAL METRICS SUCCESSFULLY SAVED TO: research/paper/evidence/FINAL_METRICS.json
```

---

## 5. Visual Figure Generation

To regenerate the publication-grade SVG figures in `research/paper/figures/`:
```powershell
.\.venv\Scripts\python.exe training/benchmarks/generate_figures.py
```
Outputs:
- `research/paper/figures/architecture_pipeline.svg`
- `research/paper/figures/confusion_matrices.svg`
- `research/paper/figures/ablation_barchart.svg`

---

## 6. Full Unit & Integration Test Suite (40 Tests)

To run the complete automated regression suite:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sr_edge_net.py tests/test_er_sp.py tests/test_cm_rp.py tests/test_r4_integration.py -v
```
Expected: **40 passed** in approximately 12.5 seconds.
