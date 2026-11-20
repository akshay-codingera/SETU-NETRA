"""
OCR subsystem package: extensible optical character recognition.
"""

from setu_netra.ocr.base import BaseOCREngine, OCREngineError, OCREngineNotFoundError
from setu_netra.ocr.mock_engine import MockOCREngine
from setu_netra.ocr.easyocr_engine import EasyOCREngine
from setu_netra.ocr.factory import get_ocr_engine, ENGINE_REGISTRY

__all__ = [
    "BaseOCREngine",
    "OCREngineError",
    "OCREngineNotFoundError",
    "MockOCREngine",
    "EasyOCREngine",
    "get_ocr_engine",
    "ENGINE_REGISTRY",
]
