"""
ocr_adapter.py: Unified OCR model adapter for SETU-NETRA.

Why this file exists:
Wraps OCR detection and recognition engines (EasyOCR, CRAFT, CRNN) behind the
unified InferenceRequest / InferenceResponse contract.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image
from setu_netra.ocr.base import BaseOCREngine
from setu_netra.ocr.factory import get_ocr_engine
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter


class OCRExecutionAdapter(BaseModelAdapter):
    """Adapter exposing OCR engines through the unified inference interface."""

    def __init__(
        self,
        engine: Optional[BaseOCREngine] = None,
        model_id: str = "easyocr-craft-crnn",
        worker_id: Optional[str] = None,
    ):
        self._engine = engine
        self._model_id = model_id
        self._worker_id = worker_id or f"{model_id}_w1"
        self._is_healthy = True

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return ["ocr", "text_extraction"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name="EasyOCR (CRAFT Text Detection + CRNN Recognition)",
            model_type=ModelCategory.OCR,
            supported_tasks=self.task_types,
            provider="JaidedAI",
            execution_backend="CPU_PYTORCH",
            memory_requirement={
                "min_ram_mb": 300,
                "recommended_ram_mb": 800,
                "quantization": "FP32",
            },
            context_length=4096,
            availability=ModelAvailability.AVAILABLE if self.is_available() else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self._is_healthy else ModelHealth.UNHEALTHY,
            throughput=2.5,
            model_quality_metadata={
                "architecture": "CRAFT + CRNN + CTC",
                "character_accuracy": 0.94,
            },
            worker_id=self.worker_id,
        )

    def _get_engine(self) -> BaseOCREngine:
        if self._engine is None:
            self._engine = get_ocr_engine("easyocr")
        return self._engine

    def is_available(self) -> bool:
        if not self._is_healthy:
            return False
        try:
            engine = self._get_engine()
            return engine.is_available()
        except Exception:
            return False

    def health_check(self) -> bool:
        return self.is_available()

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        start_time = time.perf_counter()
        if not self.is_available():
            elapsed = time.perf_counter() - start_time
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="FAILED",
                error="OCR engine is unavailable or uninitialized",
                metadata={"worker_id": self.worker_id},
            )

        try:
            payload = request.input_payload or request.prompt_or_payload
            if isinstance(payload, (str, Path)):
                img = Image.open(payload).convert("RGB")
            elif isinstance(payload, Image.Image):
                img = payload
            else:
                img = Image.fromarray(payload)

            engine = self._get_engine()
            if hasattr(engine, "recognize"):
                ocr_result = engine.recognize(img)
            elif hasattr(engine, "extract_text"):
                ocr_result = engine.extract_text(img)
            else:
                raise AttributeError(f"OCR engine {engine} has neither recognize nor extract_text")
            elapsed = time.perf_counter() - start_time

            boxes_data = [
                {
                    "text": b.text,
                    "confidence": b.confidence,
                    "bounding_box": getattr(b, "bounding_box", b.polygon),
                    "polygon": b.polygon,
                }
                for b in ocr_result.boxes
            ]

            full_text = getattr(ocr_result, "full_text", getattr(ocr_result, "raw_text", ""))

            return InferenceResponse(
                request_id=request.request_id,
                result={
                    "text": full_text,
                    "boxes": boxes_data,
                    "box_count": len(boxes_data),
                    "status": ocr_result.status,
                },
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="SUCCESS",
                metadata={
                    "box_count": len(boxes_data),
                    "engine": ocr_result.engine_name,
                    "worker_id": self.worker_id,
                },
            )
        except Exception as err:
            elapsed = time.perf_counter() - start_time
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="FAILED",
                error=str(err),
                metadata={"worker_id": self.worker_id},
            )
