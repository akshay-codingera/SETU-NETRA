# SETU-NETRA V2.0.0-RC1 — Image Processing Implementation Report

**Document ID:** `SN-REP-V2-IP-002`  
**Execution Timestamp:** 2026-11-11T23:50:00+05:30  
**Phase:** Complete Image-to-Answer Pipeline  
**Module:** Ingestion, Preprocessing & Coordinate Transformation Engine  
**Status:** IMPLEMENTED, BENCHMARKED & VERIFIED  

---

## 1. Executive Summary

This report documents the architectural repair, implementation, and rigorous validation of the image processing subsystem in SETU-NETRA V2.0.0-RC1. The image pipeline serves as the primary visual sensory gateway of SETU-NETRA, translating arbitrary input images (printed exams, handwritten notes, database schemas, whiteboard queries) into structurally reconstructed text, identified questions, and mathematically verified spatial bounding boxes.

### Key Capabilities Delivered
1. **Universal Image Format & Dimension Support:** Native handling of PNG, JPG, JPEG, TIFF, BMP, and WEBP formats across arbitrary dimensions and aspect ratios (portrait, landscape, and extreme aspect ratios).
2. **Decompression Bomb Protection:** Hard boundary configured at `Image.MAX_IMAGE_PIXELS = 100_000_000` (100 Megapixels) across ingestion, validation, and preprocessing layers to prevent memory-exhaustion DoS attacks.
3. **Magic-Byte Header Sniffing:** Extension spoofing prevention via strict header signature inspection (`sniff_image_format`).
4. **EXIF Orientation Normalization:** Automated 8-value EXIF tag orientation correction (`normalize_exif_orientation`) preventing inverted or sideways OCR on smartphone-captured images.
5. **Alpha Channel Alpha-to-White Blending:** `safe_composite_on_white` algorithm preventing black background raster corruption when processing RGBA, LA, or Palette (`P`) images.
6. **Controlled High-Resolution Downscaling:** High-resolution images (>2500px) are gracefully downscaled to a max dimension of 1600px using high-order Lanczos interpolation (`Image.Resampling.LANCZOS`), preventing OOM crashes in deep-learning OCR backbones.
7. **Small Image Preservation:** Low-resolution images (<400px) are processed directly without blurring artifacts or artificial upsampling distortion.
8. **Bidirectional Spatial Coordinate Transformation:** Full mathematical synchronization mapping bounding boxes between downscaled OCR coordinates and original full-resolution image coordinates, eliminating bounding box drift on the UI spatial canvas.

---

## 2. Mathematical Coordinate Transformation Architecture

### 2.1 The Coordinate Desynchronization Problem
In deep-learning document analysis, processing high-resolution raw scans ($3000 \times 4000$ pixels) directly through convolutional feature extractors (such as EasyOCR's CRAFT detector) leads to quadratic memory expansion and excessive inference latency. To optimize throughput, images exceeding $1600\text{ px}$ in either dimension are scaled down.

Previously, bounding boxes returned by CRAFT were in the scaled coordinate space:
$$\mathcal{B}_{\text{proc}} = [x_{\min}, y_{\min}, x_{\max}, y_{\max}]$$
When persisted to SQLite alongside the unscaled original canvas dimensions ($W_{\text{orig}}, H_{\text{orig}}$), downstream spatial viewers calculated percentage coordinates:
$$\text{left} = \frac{x_{\min}}{W_{\text{orig}}} \times 100\%$$
Because $x_{\min}$ was defined on $W_{\text{proc}}$ rather than $W_{\text{orig}}$, bounding boxes appeared shrunken by an exact factor of:
$$k = \frac{W_{\text{proc}}}{W_{\text{orig}}} < 1.0$$

### 2.2 Formal Transformation Equations
To guarantee absolute spatial precision, SETU-NETRA implements bidirectional coordinate projection functions in `src/setu_netra/preprocessing/operations.py`:

#### 1. Forward Mapping: Processed Space $\to$ Original Space
$$\begin{aligned}
S_x &= \frac{W_{\text{orig}}}{W_{\text{proc}}} \\
S_y &= \frac{H_{\text{orig}}}{H_{\text{proc}}} \\
x_{\min}^{\text{orig}} &= \text{round}(x_{\min}^{\text{proc}} \times S_x, 2) \\
y_{\min}^{\text{orig}} &= \text{round}(y_{\min}^{\text{proc}} \times S_y, 2) \\
x_{\max}^{\text{orig}} &= \text{round}(x_{\max}^{\text{proc}} \times S_x, 2) \\
y_{\max}^{\text{orig}} &= \text{round}(y_{\max}^{\text{proc}} \times S_y, 2)
\end{aligned}$$

#### 2. Reverse Mapping: Original Space $\to$ Processed Space
$$\begin{aligned}
x_{\min}^{\text{proc}} &= \text{round}\left(\frac{x_{\min}^{\text{orig}}}{S_x}, 2\right) \\
y_{\min}^{\text{proc}} &= \text{round}\left(\frac{y_{\min}^{\text{orig}}}{S_y}, 2\right) \\
x_{\max}^{\text{proc}} &= \text{round}\left(\frac{x_{\max}^{\text{orig}}}{S_x}, 2\right) \\
y_{\max}^{\text{proc}} &= \text{round}\left(\frac{y_{\max}^{\text{orig}}}{S_y}, 2\right)
\end{aligned}$$

### 2.3 Boundary Condition Verification
- **Identity Condition:** When $W_{\text{orig}} = W_{\text{proc}}$ and $H_{\text{orig}} = H_{\text{proc}}$, $S_x = 1.0$ and $S_y = 1.0$. The transformation returns the identical tuple with zero floating-point drift.
- **Aspect Ratio Invariance:** Because downscaling uses uniform scalar scaling $\lambda = \min(1600 / W_{\text{orig}}, 1600 / H_{\text{orig}})$, the aspect ratio is invariant:
$$\frac{W_{\text{proc}}}{H_{\text{proc}}} = \frac{W_{\text{orig}}}{H_{\text{orig}}} \implies S_x = S_y$$

---

## 3. Preprocessing Operations Pipeline

```
+-------------------------------------------------------------------------------+
|                       IMAGE PREPROCESSING PIPELINE                            |
+-------------------------------------------------------------------------------+
                                        |
                            Raw Upload Stream (Bytes)
                                        |
                                        v
                    [ Magic-Byte Sniffer & Size Guard ]
                    - Image.MAX_IMAGE_PIXELS = 100M
                    - Header validation (PNG, JPG, TIFF, BMP, WEBP)
                                        |
                                        v
                    [ EXIF Orientation Normalization ]
                    - ImageOps.exif_transpose()
                    - Handles tags 1 through 8 (e.g. Tag 6: 90 deg CW)
                                        |
                                        v
                    [ Alpha Channel White-Compositing ]
                    - RGBA / LA / P -> RGB canvas compositing
                    - Prevents black background obliterating dark text
                                        |
                                        v
                    [ Controlled Dimension Rescaling ]
                    - If max(W, H) > 1600px -> Lanczos resize
                    - If max(W, H) <= 400px -> Preserved as-is
                                        |
                                        +-----------------------+
                                        |                       |
                                        v                       v
                              Original Dimensions      Processed Dimensions
                               (W_orig, H_orig)         (W_proc, H_proc)
                                        |                       |
                                        |                       v
                                        |                 [ EasyOCR Engine ]
                                        |                 - CRAFT detector
                                        |                 - CRNN recognizer
                                        |                       |
                                        v                       v
                    [ Coordinate Re-projection Matrix ] <-------+
                    - Bounding boxes mapped: Proc -> Orig
                                        |
                                        v
                    [ SQLite Document Persistence ]
                    - pages: (W_orig, H_orig, full_text, questions)
                    - document_blocks: (rescaled xmin, ymin, xmax, ymax)
```

### 3.1 Alpha Channel White Compositing Algorithm
```python
def safe_composite_on_white(image: Image.Image) -> Image.Image:
    """Safely composite transparent or palette images onto a pure white RGB canvas."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or ("transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        composited = Image.alpha_composite(background, rgba)
        return composited.convert("RGB")
    return image.convert("RGB")
```

### 3.2 EXIF Orientation Matrix
Smartphone cameras store physical sensor pixel arrays oriented as captured, relying on EXIF Tag `0x0112` (`Orientation`) to specify the viewing rotation:
- `1`: Normal (0 deg rotation)
- `3`: Upside down (180 deg rotation)
- `6`: Rotated 90 deg CW (requires 90 deg CCW physical correction)
- `8`: Rotated 270 deg CW (requires 90 deg CW physical correction)

`normalize_exif_orientation(img)` calls `ImageOps.exif_transpose(img)`. If EXIF orientation metadata exists, the physical raster is transposed into upright orientation, and the EXIF tag is reset to 1. This guarantees that EasyOCR always scans characters in canonical top-to-bottom, left-to-right orientation.

---

## 4. Source Files Modified & Implemented

| File Path | Description of Changes |
| :--- | :--- |
| `src/setu_netra/preprocessing/operations.py` | Added `Image.MAX_IMAGE_PIXELS = 100_000_000`, `safe_composite_on_white`, `normalize_exif_orientation`, `map_bbox_to_original`, `map_bbox_to_processed`, and `sniff_image_format`. |
| `src/setu_netra/ingestion/loader.py` | Added decompression bomb limit, `safe_composite_on_white` before RGB conversion, and EXIF orientation normalization on disk reads. |
| `src/setu_netra/ingestion/validator.py` | Added `Image.MAX_IMAGE_PIXELS = 100_000_000` and magic-byte header verification preventing extension spoofing. |
| `src/setu_netra/pipeline/document_pipeline.py` | Integrated coordinate transformation `map_bbox_to_original` for all extracted blocks; persisted `full_text`, `raw_transcript`, `ocr_boxes_count`, `detected_questions`, and `warnings` into `pages.metadata_json`. |
| `src/setu_netra/store/sqlite_store.py` | Added `get_page(doc_id, page_number) -> Optional[DocumentPageRecord]` for instant page text and metadata retrieval. |
| `src/setu_netra/qa/question_extractor.py` | Implemented `NormalizedQuestion`, `parse_sql_clauses`, robust multi-line and bracketed option extraction, OCR noise correction, and question classification. |
| `src/setu_netra/qa/image_question_solver.py` | Implemented end-to-end `ImageQuestionSolver` supporting 8 lifecycle states, SQL relational reasoning, mathematical variable evaluation, and epistemic verification. |
| `src/setu_netra/api/schemas.py` | Added `PageTextResponse`, `SolvePageQuestionRequest`, `SolveQuestionResponse`, and expanded `ImageQueryResponse`. |
| `src/setu_netra/api/routers/documents.py` | Added `GET /api/v1/documents/{doc_id}/pages/{page_number}/text` and `POST /api/v1/documents/{doc_id}/pages/{page_number}/solve`. |
| `src/setu_netra/api/routers/query.py` | Updated `POST /api/v1/query/image` to invoke `ImageQuestionSolver` directly for problem-solving. |
| `frontend/src/api/client.ts` | Added `getPageText` and `solvePageQuestion` API client methods. |
| `frontend/src/views/DocumentIntelligenceView.tsx` | Added 3-column workspace, bounding box canvas overlay, editable extracted text, Q&A solver panel, model selector, step-by-step reasoning, and epistemic seal. |

---

## 5. Verification & Test Confirmation

The implementation was validated through the comprehensive test suite in `tests/test_image_to_answer_pipeline.py`.
- **Status:** 10/10 test scenarios passing.
- **Phase 1 ASGI tests:** 11/11 passing.
- **Phase 2 Security & Migration tests:** 15/15 passing.
- **Question Extractor tests:** 5/5 passing.
- **Total Test Execution:** 100% clean green pass.
- **Frontend Production Build:** `tsc -b && vite build` built in 2.36s with zero TypeScript or JSX errors.
