"""
mock_engine.py: Lightweight, dependency-free mock OCR engine for testing.

Why this file exists:
Modern OCR engines require heavy deep-learning dependencies (PyTorch, ONNX, CUDA)
and download multi-megabyte model checkpoints. For automated unit tests, CI/CD
pipelines, and rapid debugging, we need a deterministic engine that adheres to the
exact same contract without network access or heavy CPU execution.
"""

import time
from typing import List, Optional
from PIL import Image

from setu_netra.core.contracts import OCRBox, OCRConfig, OCRResult
from setu_netra.ocr.base import BaseOCREngine


class MockOCREngine(BaseOCREngine):
    """Deterministic, mock OCR engine for fast unit tests and dependency-free verification."""

    @property
    def engine_name(self) -> str:
        return "mock"

    @property
    def engine_version(self) -> str:
        return "1.0.0-mock"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def recognize(self, image: Image.Image, config: Optional[OCRConfig] = None) -> OCRResult:
        start_time = time.perf_counter()
        active_config = config or self.config

        # Check for completely blank / uniform image (degenerate input check)
        extrema = image.convert("L").getextrema()
        if extrema[0] == extrema[1]:
            # Uniform image (no text edges or contrast)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return OCRResult(
                engine_name=self.engine_name,
                engine_version=self.engine_version,
                boxes=[],
                raw_text="",
                processing_time_ms=round(elapsed_ms, 2),
                status="EMPTY",
                error_message="Image contains uniform pixels (no text edges detected)",
            )

        # Generate deterministic synthetic detections mapped to image geometry
        w, h = image.size
        sample_tokens = [
            ("SETU-NETRA TEST BENCH: SAMPLE QUESTION", 0.98, (0.05, 0.08, 0.65, 0.12)),
            ("Q.1) What is the computational complexity of performing 2D convolution", 0.95, (0.06, 0.18, 0.92, 0.23)),
            ("     on an image of size H x W with a kernel of size K x K?", 0.94, (0.10, 0.24, 0.85, 0.29)),
            ("[A]  O(H * W)", 0.91, (0.10, 0.35, 0.35, 0.40)),
            ("[B]  O(H * W * K^2)", 0.96, (0.10, 0.42, 0.45, 0.47)),
            ("[C]  O((H * W)^2)", 0.89, (0.10, 0.49, 0.40, 0.54)),
            ("[D]  O(K^4)", 0.92, (0.10, 0.56, 0.30, 0.61)),
            ("Note: Assume stride 1 and standard direct spatial domain computation.", 0.87, (0.06, 0.68, 0.90, 0.73)),
        ]

        boxes: List[OCRBox] = []
        for text, conf, (rx1, ry1, rx2, ry2) in sample_tokens:
            if conf < active_config.confidence_threshold:
                continue
            x1, y1 = round(rx1 * w, 1), round(ry1 * h, 1)
            x2, y2 = round(rx2 * w, 1), round(ry2 * h, 1)
            polygon = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
            boxes.append(OCRBox(polygon=polygon, text=text, confidence=conf))

        raw_text = "\n".join(b.text for b in boxes)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return OCRResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            boxes=boxes,
            raw_text=raw_text,
            processing_time_ms=round(elapsed_ms, 2),
            status="SUCCESS",
        )
