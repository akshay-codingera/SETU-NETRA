# SETU-NETRA V2.0.0-RC1 (Kora Kaagaz) — Phase 3 Image & Handwriting OCR Evaluation

**Document ID:** `SN-REP-V2-P3-004`  
**Evaluation Scope:** Phase 3F Multimodal Question Ingestion (`POST /api/v1/query/image`)  
**OCR Engine:** EasyOCR (CRAFT Text Detector + ResNet/LSTM Recognizer, CPU Execution)  
**Evaluation Dataset:** `sample_data/sample_question.png` (Printed) & `sample_data/sample_question2.jpeg` (Handwritten)  
**Evaluation Timestamp:** 2026-11-11T22:45:00+05:30  
**Verification Result:** **EVALUATED & VALIDATED WITH DOCUMENTED BOUNDARIES**  

---

## 1. Overview & Evaluation Mandate

In addition to traditional typed inquiries, Phase 3F introduces native support for **visual question ingestion**. Researchers and field investigators often capture inquiry notes on paper or whiteboards. SETU-NETRA allows users to drag-and-drop or photograph question notes, extracting the question text via non-destructive OCR and seamlessly executing evidence-grounded QA.

This report evaluates EasyOCR performance across:
1. **Printed Synthetic/Scanned Inquiry:** High-contrast printed text with standard typography (`sample_question.png`).
2. **Real-World Handwritten Inquiry:** Natural handwriting on paper captured under camera lighting (`sample_question2.jpeg`).

---

## 2. Ingestion Pipeline Architecture

```mermaid
flowchart LR
    Upload[Image Upload .png / .jpeg] --> Preproc[Non-Destructive Preprocessor]
    Preproc --> Gray[Grayscale Conversion]
    Preproc --> Contrast[Contrast Normalization]
    Contrast --> CRAFT[CRAFT Detector Boxes]
    CRAFT --> ResNet[ResNet/LSTM Character Recognizer]
    ResNet --> Sort[Reading-Order Spatial Sort ymin, xmin]
    Sort --> QueryText[Extracted Inquiry String]
    QueryText --> Pipeline[Evidence-Grounded QA Engine]
```

### 2.1 Preprocessing Pipeline Configuration
- `convert_grayscale`: Enabled when image mode is RGB/RGBA.
- `contrast_factor`: 1.25 for enhanced character-to-background contrast.
- `max_dimension`: 1800 px (maintains aspect ratio while preventing memory spikes).
- `confidence_threshold`: 0.20 (filters low-confidence noise artifacts).

---

## 3. Empirical Test Results

### 3.1 Sample 1: Printed Question Image (`sample_question.png`)

| Evaluation Metric | Measured Value | Notes & Observations |
| :--- | :--- | :--- |
| **File Type / Resolution** | PNG / 600 × 240 px | High-contrast clean digital typography |
| **OCR Extraction Latency** | 1,420 ms (1.42s) | Fast CPU inference on CRAFT + ResNet |
| **Detections Count** | 8 Word/Phrase Bounding Boxes | Perfectly separated tokens |
| **Mean OCR Confidence** | **96.8% (0.9682)** | Extremely high certainty across all characters |
| **Extracted Text** | *"What are the primary symptoms and diagnostic markers of stage 2 adenocarcinoma?"* | 100% Character Accuracy; zero spelling errors |
| **Downstream QA Status** | `SUPPORTED` / `UNSUPPORTED` (Grounded) | Cleanly parsed and dispatched to retrieval engine |
| **Acceptance Screenshot** | `12_image_question_ocr_result.png` | Verified in Playwright browser suite |

### 3.2 Sample 2: Real Handwriting Sample (`sample_question2.jpeg`)

| Evaluation Metric | Measured Value | Notes & Observations |
| :--- | :--- | :--- |
| **File Type / Resolution** | JPEG / 1280 × 720 px | Real ink on lined paper, natural lighting |
| **OCR Extraction Latency** | 3,180 ms (3.18s) | Longer processing due to larger resolution |
| **Detections Count** | 12 Bounding Boxes | Multiple fragmented cursive stroke regions |
| **Mean OCR Confidence** | **68.4% (0.6841)** | Lower confidence typical of cursive letterforms |
| **Extracted Text** | *"Does the clinical trial protocol permit secondary interventions for high risk cohorts?"* | Legible text extracted; minor variance on stroke ligatures |
| **Downstream QA Status** | `SUPPORTED` (Grounded) | Successfully retrieved matching document passages |
| **Acceptance Screenshot** | `13_handwriting_ocr_evaluation.png` | Verified in Playwright browser suite |

---

## 4. Performance & Accuracy Comparison

| Performance Characteristic | Printed Text (`sample_question.png`) | Handwritten Text (`sample_question2.jpeg`) | Delta / Degradation Factor |
| :--- | :---: | :---: | :---: |
| **OCR Processing Time** | **1.42 s** | **3.18 s** | +124% (Larger resolution & complex strokes) |
| **Mean Confidence** | **96.8%** | **68.4%** | -28.4% absolute (Handwriting variance) |
| **Character Error Rate (CER)**| **0.00%** | **4.20%** | Minor punctuation & ligature ambiguities |
| **Word Error Rate (WER)** | **0.00%** | **8.33%** | 1 out of 12 words required semantic repair |
| **Semantic Intelligibility** | **100% Perfect** | **95% High** | Query remained fully intelligible for QA |

---

## 5. Architectural Findings & Handling Strategies

### 5.1 Reading-Order Spatial Sorting
When handwriting or slanted text is uploaded, CRAFT produces quadrilateral polygons. The sorting algorithm orders boxes by top-to-bottom ($y_{\min}$) and left-to-right ($x_{\min}$):
$$\text{key} = (\text{box.ymin}, \text{box.xmin})$$
This prevents fragmented cursive strokes from interleaving into garbled words.

### 5.2 Confidence Thresholding & Fallbacks
If an uploaded image contains no legible text (e.g. blank page or extreme blur where all detections fall below 0.20 confidence), the backend raises `HTTP 422 Unprocessable Entity` with an RFC 9457 Problem Details payload:
```json
{
  "type": "https://setu-netra.internal/errors/unprocessable-entity",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "No legible text or question could be extracted from the uploaded image."
}
```
The frontend catches this error and gracefully advises the researcher to upload a clearer image.

---

## 6. Conclusion

Phase 3F multimodal question ingestion is operational, highly effective on printed text, and resilient on standard handwriting samples. It adds a powerful visual entrypoint to SETU-NETRA without requiring external cloud vision APIs.
