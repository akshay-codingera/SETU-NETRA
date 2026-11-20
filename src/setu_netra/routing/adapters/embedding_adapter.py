"""
embedding_adapter.py: Unified embedding model adapter for SETU-NETRA.

Why this file exists:
Wraps sentence transformers and offline semantic feature hashing engines behind
the unified InferenceRequest / InferenceResponse interface contract.
"""

import time
from typing import Any, Dict, List, Optional
import numpy as np
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine


class EmbeddingExecutionAdapter(BaseModelAdapter):
    """Adapter exposing embedding models through the unified inference interface."""

    def __init__(
        self,
        engine: Optional[BaseEmbeddingEngine] = None,
        model_id: Optional[str] = None,
        worker_id: Optional[str] = None,
    ):
        self._engine = engine or get_embedding_engine()
        self._model_id = model_id or self._engine.engine_name
        self._worker_id = worker_id or f"{self._model_id}_w1"
        self._is_healthy = True

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def task_types(self) -> List[str]:
        return ["embedding", "similarity"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name=f"Embedding Engine ({self._engine.engine_name})",
            model_type=ModelCategory.EMBEDDING,
            supported_tasks=self.task_types,
            provider="Sentence-Transformers",
            execution_backend="CPU_PYTORCH" if "minilm" in self._model_id.lower() else "LOCAL_PYTHON",
            memory_requirement={
                "min_ram_mb": 80,
                "recommended_ram_mb": 250,
                "quantization": "FP32",
            },
            context_length=256,
            availability=ModelAvailability.AVAILABLE if self.is_available() else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self._is_healthy else ModelHealth.UNHEALTHY,
            throughput=50.0,
            model_quality_metadata={
                "dimension": self._engine.dimension,
                "normalized": True,
            },
            worker_id=self.worker_id,
        )

    def is_available(self) -> bool:
        return self._is_healthy and self._engine.is_available()

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
                error="Embedding engine is currently unavailable",
                metadata={"worker_id": self.worker_id},
            )

        try:
            payload = request.input_payload or request.prompt_or_payload
            if isinstance(payload, str):
                texts = [payload]
            elif isinstance(payload, (list, tuple)):
                texts = [str(x) for x in payload]
            else:
                texts = [str(payload)]

            embeddings = self._engine.embed_texts(texts)
            elapsed = time.perf_counter() - start_time

            return InferenceResponse(
                request_id=request.request_id,
                result=embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="SUCCESS",
                metadata={
                    "dimension": self._engine.dimension,
                    "batch_size": len(texts),
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
