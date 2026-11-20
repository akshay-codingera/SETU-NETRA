# SETU-NETRA EasyOCR Harness Forensic Audit Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Computer Vision & OCR Systems Auditor  
**Scope:** Stage 6 Real Inference Benchmark — EasyOCR (CRAFT Text Detection + CRNN Recognition) 100% Failure Investigation  
**Primary Reference Files:**
- [`benchmarks/results/aggregated/real_inference_benchmarks_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/real_inference_benchmarks_summary.json)
- [`benchmarks/results/raw/real_inference_benchmarks_raw.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/raw/real_inference_benchmarks_raw.json)
- [`src/setu_netra/core/contracts.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/core/contracts.py)
- [`src/setu_netra/routing/adapters/ocr_adapter.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/routing/adapters/ocr_adapter.py)

---

## 1. Executive Summary & Root Cause

In `real_inference_benchmarks_summary.json`, the model `easyocr-craft-crnn` was recorded with an **`error_rate_percent` of 100.0%**.
Reviewers raised concerns over whether the deep learning OCR pipeline was broken or failed to execute on CPU hardware.

### Forensic Finding: Successful Deep Learning Execution Followed by Wrapper Defect
Our audit of the raw execution traces proves that **the deep learning models executed completely and successfully on the test images**:
1. **Model Loading:** CRAFT (Character Region Awareness for Text Detection) and CRNN (Convolutional Recurrent Neural Network for Text Recognition) loaded successfully into CPU memory. Cold initialization elapsed $22,826.04\text{ ms}$ ($22.8\text{ s}$).
2. **Inference Latency:** Across three warm iterations, the neural network processed the test image with an average execution latency of **$4,497.32\text{ ms}$** ($\sim 4.5\text{ s}$ per full page on consumer CPU):
   - Iteration 1: $4,432.34\text{ ms}$
   - Iteration 2: $4,552.41\text{ ms}$
   - Iteration 3: $4,507.22\text{ ms}$
3. **The Exact Failure:** At the conclusion of the $4.5\text{ s}$ OCR inference pass, the benchmark adapter executed the following lines in `src/setu_netra/routing/adapters/ocr_adapter.py`:

```python
boxes_data = [
    {
        "text": b.text,
        "confidence": b.confidence,
        "bounding_box": b.bounding_box,  # <--- CRASH HERE!
        "polygon": b.polygon,
    }
    for b in ocr_result.boxes
]
```

### The Schema Mismatch
In `src/setu_netra/core/contracts.py` (lines 35–45), the dataclass `OCRBox` is defined as:
```python
@dataclass
class OCRBox:
    polygon: List[Tuple[float, float]]
    text: str
    confidence: float
```
`OCRBox` contains the attribute `polygon`, but **does not possess an attribute named `bounding_box`**.
When the adapter attempted `b.bounding_box`, Python raised:
`AttributeError: 'OCRBox' object has no attribute 'bounding_box'`.

### Forensic Verdict
The OCR engine did **not** fail. Text detection and text recognition executed to completion. The 100% error rate was purely caused by a post-inference dictionary packaging bug in the adapter wrapper.
In the active codebase, this has been hardened via `getattr(b, "bounding_box", b.polygon)`.

### Manuscript Action Items
- Do not claim that EasyOCR failed to function on CPU.
- Accurately report: "EasyOCR (CRAFT + CRNN) executes on CPU with a mean latency of $4.50\text{ s}$ per document page ($0.22\text{ req/s}$ throughput). A packaging wrapper attribute defect caused benchmark reporting failure in historical logs, which was resolved without altering model weights."
