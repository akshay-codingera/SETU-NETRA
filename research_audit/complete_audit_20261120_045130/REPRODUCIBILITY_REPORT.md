# SETU-NETRA Comprehensive Reproducibility Report

This document records the exact runtime environment, commands, random seeds, hardware specifications, dataset paths, checkpoint hashes, and evaluation protocols required to independently reproduce all reported experimental findings of the SETU-NETRA research project.

---

## 1. System and Hardware Environment

| Property | Value Observed During Audit |
| :--- | :--- |
| **Operating System** | Windows 11 Home / Pro (Windows-11-10.0.26200-SP0) |
| **Platform Architecture** | AMD64 (x86_64) |
| **CPU Model** | Intel(R) Core(TM) i7-13650HX / GenuineIntel Family 6 Model 186 Stepping 3 |
| **Physical / Logical Cores** | 10 Physical Cores / 12 Logical Processors |
| **Host Total RAM** | 15.65 GB (16,027.7 MB) |
| **Host Available RAM** | ~1.73 GB to 3.67 GB during execution |
| **GPU / Accelerator** | None active (CUDA Available: False, CPU-Only Execution strictly enforced) |
| **Python Runtime** | Python 3.14.7 (tags/v3.14.7:823f032, Aug 5 2026) [MSC v.1944 64 bit] |
| **Virtual Environment** | `d:\Projects\Setu-Netra\.venv` |

---

## 2. Core Python Dependencies

| Package | Version | Purpose in SETU-NETRA |
| :--- | :--- | :--- |
| `torch` | `2.14.1+cpu` | Neural model execution (SR-EdgeNet, ER-SP, CM-RP) |
| `sentence-transformers` | `2.2.2` | Dense sentence embedding (`all-MiniLM-L6-v2`) |
| `transformers` | `4.38.2` | Local SLM inference (`SmolLM2-135M-Instruct`) |
| `scikit-learn` | `1.4.1.post1` | Evaluation metrics, confusion matrices, calibration curves |
| `numpy` | `1.26.4` | Matrix computations, geometry processing, feature vectors |
| `scipy` | `1.12.0` | Statistical tests (McNemar, binomial exact test, chi-square) |
| `sympy` | `1.12` | Symbolic arithmetic and algebraic expression solver |
| `easyocr` | `1.7.0` | CRAFT text detector and CRNN recognition |
| `fastapi` | `0.110.0` | Production REST API service |
| `psutil` | `5.9.8` | Host CPU, RAM, and process telemetry probes |
| `matplotlib` | `3.8.3` | High-resolution publication chart generation |
| `reportlab` | `4.1.0` | Camera-ready IEEE PDF paper generation |

---

## 3. Checkpoint Manifest & Cryptographic Hashes

All model weights are stored in the `models/` directory. Hashes were verified before and during this audit:

| Model Component | File Path | Parameters | File Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **R1: SR-EdgeNet** | `models/structure/sr_edge_net.pt` | 414,088 | 5,005,767 | `cc1ab954c43930d12f11fcb631d5c2e0b12fcfe93108d13a9d20c529ba4266c1` |
| **R1: SR-EdgeNet (FUNSD Only)** | `models/structure/sr_edge_net_funsd_only.pt` | 414,088 | 5,007,217 | `a3aea3819f970090f77977a41ecdd59954d6faeb6fdf538eebe01f2f81ec3ff7` |
| **R1: SR-EdgeNet (Synth Only)** | `models/structure/sr_edge_net_synth_only.pt` | 414,088 | 5,007,217 | `235366a3e8e291807d4b459c3f4e2f893d5f30e620577df0f0beaf736655c654` |
| **R2: ER-SP** | `models/evidence/er_sp.pt` | 560,134 | 6,738,711 | `c44d7e77be93b55639655f448c407548074d6c29c8e9b67484df6f9e8a93aa5e` |
| **R3: CM-RP (v1)** | `models/policy/cm_rp.pt` | 63,367 | 771,855 | `5f8b1757d11dd0125740fc67848c0a87a1cf27599052d9b64cfa99d4285ad427` |
| **R3: CM-RP (v2)** | `models/policy/cm_rp_v2.pt` | 63,367 | 773,721 | `eb37cabe0d233ea3e414f6bdf67586ff90b4d45543c8d1976a4dfc01bc89ea52` |

---

## 4. Dataset Splits and Partitioning

### 4.1 SETU-SR (R1 Structure)
- **Train split**: `training/datasets/SETU-SR/splits/train.jsonl` (36,346 edges)
- **Validation split**: `training/datasets/SETU-SR/splits/val.jsonl` (6,584 edges)
- **Synthetic test split**: `training/datasets/SETU-SR/splits/test_synthetic.jsonl` (4,423 edges)
- **In-domain gold split**: `training/datasets/SETU-SR/splits/test_in_domain.jsonl` (204 edges)
- **Total edges**: 47,557 edges across 459 document units. Zero edge leakage verified across splits.

### 4.2 SETU-ER (R2 Evidence)
- **Train split**: `training/datasets/SETU-ER/splits/train.jsonl` (1,560 records across 12 disjoint CS topics)
- **Validation split**: `training/datasets/SETU-ER/splits/val.jsonl` (340 records across 4 disjoint CS topics)
- **Unseen test split**: `training/datasets/SETU-ER/splits/test.jsonl` (340 records across 4 held-out topics: 2PC, B+ Tree, Master Theorem, DNS)
- **In-domain gold split**: `training/datasets/SETU-ER/splits/test_in_domain.jsonl` (12 real document queries)
- **Total records**: 2,252 records. Classes strictly balanced at 68 samples/class on validation and unseen test sets.

### 4.3 SETU-CM (R3 Policy)
- **Train split**: `training/datasets/SETU-CM/splits/train.jsonl` (1,900 samples)
- **Validation split**: `training/datasets/SETU-CM/splits/val.jsonl` (340 samples)
- **Independent 7-Action test**: `training/datasets/SETU-CM/splits/test_7action_independent.jsonl` (245 samples, exactly 35 balanced samples per action)
- **Held-out gold test**: `training/datasets/SETU-CM/splits/test_in_domain.jsonl` (10 real document queries)

---

## 5. Exact Execution Commands

To reproduce the benchmark evaluations independently:

### 5.1 R1 Evaluation
```powershell
.\.venv\Scripts\python.exe training\structure\evaluate.py --checkpoint models\structure\sr_edge_net.pt --test-split training\datasets\SETU-SR\splits\test_synthetic.jsonl
```

### 5.2 R2 Evaluation
```powershell
.\.venv\Scripts\python.exe training\evidence\evaluate.py --checkpoint models\evidence\er_sp.pt --test-split training\datasets\SETU-ER\splits\test.jsonl
```

### 5.3 R3 Independent 7-Action Evaluation
```powershell
.\.venv\Scripts\python.exe training\policy\evaluate.py --checkpoint models\policy\cm_rp_v2.pt --test-split training\datasets\SETU-CM\splits\test_7action_independent.jsonl
```

### 5.4 R4 Full Integration & Critical Audit Suite
```powershell
.\.venv\Scripts\python.exe training\benchmarks\evaluate_critical_audit.py
```

### 5.5 Runtime Scheduler & Reliability Microbenchmarks
```powershell
.\.venv\Scripts\python.exe benchmarks\run_full_evaluation.py
```

---

## 6. Reproducibility Limitations & Caveats

1. **Host CPU Load Jitter**: In multi-worker concurrent scheduler benchmarks, thread dispatch overhead on Windows 11 experiences $\pm 5$ to $10\ \mu\text{s}$ variation depending on background OS activity and power throttling profiles.
2. **EasyOCR Benchmark Attribute Bug**: The raw inference benchmark script (`benchmarks/runners/inference_runner.py`) will report 100% error rate on EasyOCR unless patched to read `box.polygon` or `box.xmin` instead of `box.bounding_box`.
3. **SymPy Mathematical Strictness**: Mathematical expression extraction from natural language queries (e.g., `"calculate total_speedup = 1 / ((1 - p) + (p / s))"`) requires stripping prose phrases before passing to `sympy.sympify()`; unstripped queries default to Extractive QA fallback.
4. **Ollama Daemon Dependency**: Local SLM execution (`Qwen 3.5 2B`) requires an active local background daemon listening on `127.0.0.1:11434`; if offline, the pipeline gracefully falls back to `SmolLM2-135M-Instruct` or `EXTRACTIVE_QA`.
