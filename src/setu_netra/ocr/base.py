"""
base.py: Abstract Base Class (Interface) for OCR engines in SETU-NETRA.

Why this file exists:
To prevent tight coupling between our application and any single proprietary or
open-source OCR library (like PaddleOCR, EasyOCR, or Tesseract), we establish an
abstract contract. Downstream pipelines only interact with `BaseOCREngine`.
"""

from abc import ABC, abstractmethod
from typing import Optional
from PIL import Image

from setu_netra.core.contracts import OCRConfig, OCRResult


class OCREngineError(Exception):
    """Raised when an OCR engine encounters an unrecoverable inference error."""
    pass


class OCREngineNotFoundError(OCREngineError):
    """Raised when the requested OCR engine or its dependencies are not installed."""
    pass


class BaseOCREngine(ABC):
    """Abstract Base Class for OCR engines.

    Every concrete OCR adapter must implement this interface, guaranteeing:
    1. Input acceptance as an in-memory PIL Image.
    2. Output normalized as an OCRResult containing standardized OCRBox items.
    3. Non-mutation of the input image.
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Identifying name of the engine (e.g. 'easyocr', 'paddleocr', 'mock')."""
        pass

    @property
    @abstractmethod
    def engine_version(self) -> str:
        """Version string of the underlying library or model weights."""
        pass

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if all third-party dependencies are importable and functional."""
        pass

    @abstractmethod
    def recognize(self, image: Image.Image, config: Optional[OCRConfig] = None) -> OCRResult:
        """Perform text detection and recognition on an in-memory PIL Image.

        Args:
            image: In-memory PIL Image. Must not be mutated in-place.
            config: Optional override of default OCR configuration.

        Returns:
            OCRResult containing detected bounding boxes, recognized strings,
            confidence scores, and timing metrics.
        """
        pass
