"""
interfaces.py: Abstract base class for all SETU-NETRA model adapters.

Why this file exists:
Decouples application code from concrete model backends (PyTorch CPU, GGUF, local
extractive rules, remote APIs), ensuring complete pluggability across OCR, embedding,
classification, extractive QA, and generative QA tasks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)


class BaseModelAdapter(ABC):
    """Abstract interface contract for all model execution adapters."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Identifying name of the model."""
        pass

    @property
    def worker_id(self) -> str:
        """Identifier for a specific worker instance of the model."""
        return getattr(self, "_worker_id", f"{self.model_id}_w1")

    @property
    @abstractmethod
    def task_types(self) -> List[str]:
        """List of supported task types (e.g. ['qa', 'summarization'])."""
        pass

    @property
    def metadata(self) -> ModelMetadata:
        """Model descriptor metadata."""
        if hasattr(self, "_metadata") and self._metadata is not None:
            return self._metadata
        # Default fallback descriptor
        return ModelMetadata(
            model_id=self.model_id,
            model_name=self.model_id,
            model_type=ModelCategory.EXTRACTIVE_QA,
            supported_tasks=self.task_types,
            provider="SETU-NETRA Native",
            execution_backend="LOCAL_PYTHON",
            memory_requirement={"min_ram_mb": 50, "recommended_ram_mb": 100},
            context_length=2048,
            availability=ModelAvailability.AVAILABLE if self.is_available() else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self.is_available() else ModelHealth.UNHEALTHY,
            worker_id=self.worker_id,
        )

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether local weights or execution dependencies are ready."""
        pass

    def health_check(self) -> bool:
        """Perform a quick operational health probe on the adapter."""
        try:
            return self.is_available()
        except Exception:
            return False

    @abstractmethod
    def execute(self, request: InferenceRequest) -> InferenceResponse:
        """Execute inference synchronously against the adapter.

        Args:
            request: InferenceRequest containing input_payload, task_type, timeout, etc.

        Returns:
            InferenceResponse containing result, latency, status, and error details.
        """
        pass
