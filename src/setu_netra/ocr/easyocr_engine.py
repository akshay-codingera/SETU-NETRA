"""
easyocr_engine.py: Real open-source OCR adapter using EasyOCR (CRAFT + CRNN).

Why this file exists:
EasyOCR provides state-of-the-art deep-learning-based text detection (CRAFT) and
recognition (CRNN) that executes reliably on CPU without requiring proprietary
cloud APIs or external binary installations like Tesseract. This module wraps
EasyOCR behind the BaseOCREngine contract.
"""

import time
from typing import List, Optional
import numpy as np
from PIL import Image

from setu_netra.core.contracts import OCRBox, OCRConfig, OCRResult
from setu_netra.ocr.base import BaseOCREngine, OCREngineError, OCREngineNotFoundError


class EasyOCREngine(BaseOCREngine):
    """Production-grade adapter for EasyOCR."""

    def __init__(self, config: Optional[OCRConfig] = None):
        super().__init__(config=config)
        self._reader = None
        self._version = "unknown"

    @property
    def engine_name(self) -> str:
        return "easyocr"

    @property
    def engine_version(self) -> str:
        if self._version == "unknown":
            try:
                import easyocr
                self._version = getattr(easyocr, "__version__", "1.7.x")
            except ImportError:
                self._version = "not-installed"
        return self._version

    @classmethod
    def is_available(cls) -> bool:
        try:
            import easyocr  # noqa: F401
            import torch    # noqa: F401
            return True
        except ImportError:
            return False

    def _get_reader(self):
        """Lazily initialize the EasyOCR reader on first inference."""
        if self._reader is None:
            if not self.is_available():
                raise OCREngineNotFoundError(
                    "EasyOCR is not installed or dependencies (torch/torchvision) are missing. "
                    "Install via: pip install easyocr"
                )
            import easyocr
            # Force CPU execution for laptop compatibility
            languages = list(self.config.languages)
            self._reader = easyocr.Reader(languages, gpu=self.config.use_gpu)
        return self._reader

    def recognize(self, image: Image.Image, config: Optional[OCRConfig] = None) -> OCRResult:
        start_time = time.perf_counter()
        active_config = config or self.config

        # 1. Acquire reader instance
        try:
            reader = self._get_reader()
        except Exception as err:
            raise OCREngineError(f"Failed to initialize EasyOCR engine: {err}") from err

        # 2. Defensive check for empty or corrupt image
        if image.width == 0 or image.height == 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return OCRResult(
                engine_name=self.engine_name,
                engine_version=self.engine_version,
                boxes=[],
                raw_text="",
                processing_time_ms=round(elapsed_ms, 2),
                status="EMPTY",
                error_message="Image has zero dimensions",
            )

        # 3. Convert PIL Image to RGB NumPy array without mutating original
        img_np = np.array(image.convert("RGB"))

        # 4. Perform inference
        try:
            # detail=1 returns list of: [ [ [x1,y1], [x2,y2], [x3,y3], [x4,y4] ], text, confidence ]
            # (or [poly, text] if paragraph=True)
            raw_detections = reader.readtext(
                img_np,
                detail=active_config.detail,
                paragraph=active_config.paragraph,
                add_margin=active_config.add_margin,
                mag_ratio=active_config.mag_ratio,
                text_threshold=active_config.text_threshold,
                low_text=active_config.low_text,
                link_threshold=active_config.link_threshold,
            )
        except Exception as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return OCRResult(
                engine_name=self.engine_name,
                engine_version=self.engine_version,
                boxes=[],
                raw_text="",
                processing_time_ms=round(elapsed_ms, 2),
                status="FAILED",
                error_message=f"Inference exception in EasyOCR: {err}",
            )

        # 5. Transform raw vendor outputs into standard OCRBox items
        boxes: List[OCRBox] = []
        for item in raw_detections:
            if len(item) == 3:
                raw_poly, text, conf = item
                conf_val = float(conf)
            elif len(item) == 2:
                raw_poly, text = item
                conf_val = 1.0
            else:
                continue

            if conf_val < active_config.confidence_threshold:
                continue

            # Ensure polygon is tuple of (float, float)
            polygon = tuple(
                (float(pt[0]), float(pt[1]))
                for pt in raw_poly
            )
            boxes.append(OCRBox(
                polygon=polygon,
                text=str(text).strip(),
                confidence=round(conf_val, 4),
            ))

        raw_text = "\n".join(b.text for b in boxes if b.text)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        status = "SUCCESS" if boxes else "EMPTY"

        return OCRResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            boxes=boxes,
            raw_text=raw_text,
            processing_time_ms=round(elapsed_ms, 2),
            status=status,
            error_message="No text detected above confidence threshold" if not boxes else None,
        )
