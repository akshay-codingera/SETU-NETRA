"""
factory.py: Central factory and registry for instantiating OCR engines.

Why this file exists:
In accordance with the Dependency Inversion Principle, client code should request
an engine through a factory rather than instantiating vendor-specific classes directly.
This allows seamless switching between EasyOCR, PaddleOCR, Tesseract, and Mock engines.
"""

from typing import Dict, Optional, Type

from setu_netra.core.contracts import OCRConfig
from setu_netra.ocr.base import BaseOCREngine, OCREngineNotFoundError
from setu_netra.ocr.mock_engine import MockOCREngine
from setu_netra.ocr.easyocr_engine import EasyOCREngine


ENGINE_REGISTRY: Dict[str, Type[BaseOCREngine]] = {
    "easyocr": EasyOCREngine,
    "mock": MockOCREngine,
}


def get_ocr_engine(
    engine_name: Optional[str] = None,
    config: Optional[OCRConfig] = None,
) -> BaseOCREngine:
    """Instantiate and return an OCR engine matching the specified name.

    Args:
        engine_name: Name of the engine ('easyocr', 'mock', or 'auto').
                     Defaults to the engine specified in config or 'easyocr'.
        config: Configuration options for the engine.

    Returns:
        An instance conforming to BaseOCREngine.

    Raises:
        OCREngineNotFoundError: If the engine name is unknown or requested engine is missing.
    """
    cfg = config or OCRConfig()
    target_name = (engine_name or cfg.engine_name).lower()

    if target_name == "auto":
        # Auto-selection: Prefer real engine if dependencies exist, else Mock with warning
        if EasyOCREngine.is_available():
            target_name = "easyocr"
        else:
            target_name = "mock"

    if target_name not in ENGINE_REGISTRY:
        supported = list(ENGINE_REGISTRY.keys()) + ["auto"]
        raise OCREngineNotFoundError(
            f"Unsupported OCR engine '{target_name}'. Supported engines: {supported}"
        )

    engine_cls = ENGINE_REGISTRY[target_name]
    return engine_cls(config=cfg)
