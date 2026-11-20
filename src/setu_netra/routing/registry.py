"""
registry.py: Centralized, extensible Model Registry and Execution Hub for SETU-NETRA Stage 4.

Why this file exists:
Provides a thread-safe, centralized catalog of all model adapters (OCR, Embedding,
Classification, Extractive QA, Generative QA, Summarization, Reasoning). Tracks dynamic
availability, operational health, measured latency, throughput, quality profiles, and
worker instances. Serves as the bedrock for adaptive model routing and capacity scheduling.
"""

import threading
import time
from typing import Any, Dict, List, Optional
from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.cloud_adapters import GeminiCloudAdapter, GroqCloudAdapter, OpenRouterCloudAdapter
from setu_netra.routing.adapters.embedding_adapter import EmbeddingExecutionAdapter
from setu_netra.routing.adapters.generative_adapter import LocalGenerativeAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.adapters.ocr_adapter import OCRExecutionAdapter
from setu_netra.routing.adapters.ollama_adapter import OllamaProviderAdapter
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter


class ModelRegistry:
    """Thread-safe centralized registry of model adapters and execution workers."""

    def __init__(self, register_defaults: bool = True):
        self._lock = threading.RLock()
        self._adapters: Dict[str, BaseModelAdapter] = {}               # Primary map: model_id -> primary adapter
        self._workers: Dict[str, List[BaseModelAdapter]] = {}          # Multi-worker map: model_id -> list of worker adapters
        self._metadata: Dict[str, ModelMetadata] = {}                  # model_id -> ModelMetadata
        self._telemetry: Dict[str, Dict[str, Any]] = {}                # model_id -> telemetry stats
        self._worker_indices: Dict[str, int] = {}                      # model_id -> round-robin pointer

        if register_defaults:
            self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register default core model adapters for each supported category."""
        # 1. Extractive QA (Native CPU, zero-download default)
        extractive = GroundedExtractiveQAAdapter()
        self.register_adapter(extractive, allow_override=True)

        # 2. Local Generative QA (SmolLM2-135M-Instruct on local CPU)
        generative = LocalGenerativeAdapter()
        self.register_adapter(generative, allow_override=True)

        # 3. Embedding Engine (all-MiniLM-L6-v2)
        embedding = EmbeddingExecutionAdapter()
        self.register_adapter(embedding, allow_override=True)

        # 4. OCR Engine (EasyOCR CRAFT + CRNN)
        ocr = OCRExecutionAdapter()
        self.register_adapter(ocr, allow_override=True)

        # 5. Classification (Academic Domain & Intent)
        classifier = ClassificationExecutionAdapter()
        self.register_adapter(classifier, allow_override=True)

        # 6. Local Ollama Provider (Qwen 3.5 2B default)
        ollama = OllamaProviderAdapter(model_name="qwen3.5:2b")
        self.register_adapter(ollama, allow_override=True)

        # 7. Cloud Model Providers (Graceful NOT_CONFIGURED when no key provided)
        gemini = GeminiCloudAdapter(model_name="gemini-2.5-flash", model_id="gemini/gemini-2.5-flash")
        self.register_adapter(gemini, allow_override=True)
        gemini_legacy = GeminiCloudAdapter(model_name="gemini-2.0-flash", model_id="google/gemini-2.0-flash")
        self.register_adapter(gemini_legacy, allow_override=True)

        groq = GroqCloudAdapter(model_name="llama-3.3-70b-versatile", model_id="groq/llama-3.3-70b-versatile")
        self.register_adapter(groq, allow_override=True)
        groq_fast = GroqCloudAdapter(model_name="llama-3.1-8b-instant", model_id="groq/llama-3.1-8b-instant")
        self.register_adapter(groq_fast, allow_override=True)

        openrouter = OpenRouterCloudAdapter()
        self.register_adapter(openrouter, allow_override=True)

    def register_adapter(
        self,
        adapter: BaseModelAdapter,
        allow_override: bool = False,
        metadata: Optional[ModelMetadata] = None,
        override: Optional[bool] = None,
    ) -> None:
        """Register a model adapter or a worker instance of an existing model.

        Args:
            adapter: Concrete BaseModelAdapter instance.
            allow_override: If False, raises ValueError on duplicate model_id + worker_id.
            metadata: Optional explicit ModelMetadata descriptor.
            override: Alias for allow_override.
        """
        if override is not None:
            allow_override = override
        with self._lock:
            m_id = adapter.model_id
            w_id = adapter.worker_id

            # Check if this model_id exists
            if m_id in self._adapters:
                existing_workers = self._workers.get(m_id, [])
                worker_ids = [w.worker_id for w in existing_workers]

                # If same worker_id is being re-registered
                if w_id in worker_ids:
                    if not allow_override:
                        raise ValueError(
                            f"Model adapter '{m_id}' with worker ID '{w_id}' is already registered. "
                            f"Use allow_override=True to replace."
                        )
                    # Replace the existing worker instance
                    self._workers[m_id] = [w for w in existing_workers if w.worker_id != w_id]

                # Add new worker to the model worker pool
                self._workers[m_id].append(adapter)
            else:
                self._adapters[m_id] = adapter
                self._workers[m_id] = [adapter]
                self._worker_indices[m_id] = 0

            # Register metadata
            meta = metadata or adapter.metadata
            self._metadata[m_id] = meta

            # Initialize telemetry if not present
            if m_id not in self._telemetry:
                self._telemetry[m_id] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "timeout_count": 0,
                    "total_latency_ms": 0.0,
                    "latencies_ms": [],
                    "last_error": None,
                    "last_called_at": 0.0,
                }

    def unregister_adapter(self, model_id: str, worker_id: Optional[str] = None) -> bool:
        """Remove a model or specific worker from the registry."""
        with self._lock:
            if model_id not in self._adapters:
                return False

            if worker_id is not None:
                # Remove specific worker
                workers = self._workers.get(model_id, [])
                new_workers = [w for w in workers if w.worker_id != worker_id]
                if len(new_workers) == len(workers):
                    return False
                self._workers[model_id] = new_workers
                if not new_workers:
                    del self._adapters[model_id]
                    self._metadata.pop(model_id, None)
                    self._telemetry.pop(model_id, None)
                elif self._adapters[model_id].worker_id == worker_id:
                    self._adapters[model_id] = new_workers[0]
                return True
            else:
                # Remove entire model family
                del self._adapters[model_id]
                self._workers.pop(model_id, None)
                self._metadata.pop(model_id, None)
                self._telemetry.pop(model_id, None)
                self._worker_indices.pop(model_id, None)
                return True

    def _resolve_model_id(self, model_id: str) -> str:
        """Resolve aliases like 'qwen3.5:2b' or 'ollama' to canonical model IDs."""
        if model_id in self._adapters:
            return model_id
        if f"ollama/{model_id}" in self._adapters:
            return f"ollama/{model_id}"
        if model_id.lower() in ("ollama", "local-slm", "qwen", "qwen3.5"):
            for k in self._adapters:
                if k.startswith("ollama/"):
                    return k
        return model_id

    def get_adapter(self, model_id: str, worker_id: Optional[str] = None) -> Optional[BaseModelAdapter]:
        """Retrieve model adapter by model ID and optional worker ID.

        If worker_id is omitted, returns an available worker using round-robin.
        """
        with self._lock:
            canonical_id = self._resolve_model_id(model_id)
            if canonical_id not in self._adapters:
                return None

            workers = self._workers.get(canonical_id, [])
            if not workers:
                return self._adapters.get(canonical_id)

            if worker_id is not None:
                for w in workers:
                    if w.worker_id == worker_id:
                        return w
                return None

            # Round-robin selection among available workers
            available_workers = [w for w in workers if w.is_available()]
            if not available_workers:
                return workers[0]

            idx = self._worker_indices.get(canonical_id, 0) % len(available_workers)
            selected = available_workers[idx]
            self._worker_indices[canonical_id] = (idx + 1) % len(available_workers)
            return selected

    def get_registered_model_ids(self) -> List[str]:
        """List all unique registered model IDs."""
        with self._lock:
            return list(self._adapters.keys())

    def get_registered_models(self, available_only: bool = False) -> List[ModelMetadata]:
        """Retrieve ModelMetadata objects for all registered models."""
        with self._lock:
            models: List[ModelMetadata] = []
            for m_id, meta in self._metadata.items():
                if available_only:
                    adapter = self._adapters.get(m_id)
                    if not adapter or not adapter.is_available() or meta.availability != ModelAvailability.AVAILABLE:
                        continue
                models.append(meta)
            return models

    def get_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve rich ModelMetadata for a model."""
        return self.get_metadata(model_id)

    def get_workers_for_model(self, model_id: str) -> List[BaseModelAdapter]:
        """Return list of all registered worker adapters for a model."""
        with self._lock:
            return list(self._workers.get(model_id, []))

    def get_models_by_category(self, category: Any) -> List[ModelMetadata]:
        """Retrieve registered models belonging to a specific ModelCategory."""
        cat_val = category.value if hasattr(category, "value") else str(category).lower()
        with self._lock:
            return [
                m for m in self._metadata.values()
                if (m.model_type.value.lower() if hasattr(m.model_type, "value") else str(m.model_type).lower()) == cat_val
            ]

    def set_model_availability(self, model_id: str, availability: Any) -> bool:
        """Set model availability using string or ModelAvailability enum."""
        avail_val = availability.value if hasattr(availability, "value") else str(availability)
        return self.set_availability(model_id, avail_val)

    def set_model_health(self, model_id: str, health: Any) -> bool:
        """Set model health status using string or ModelHealth enum."""
        health_val = health.value if hasattr(health, "value") else str(health)
        return self.set_health_status(model_id, health_val)

    def list_workers(self, model_id: str) -> List[str]:
        """List worker IDs registered for a given model."""
        with self._lock:
            return [w.worker_id for w in self._workers.get(model_id, [])]

    def get_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve rich ModelMetadata for a model."""
        with self._lock:
            canonical_id = self._resolve_model_id(model_id)
            return self._metadata.get(canonical_id)

    def list_models(
        self,
        filter_task: Optional[str] = None,
        filter_category: Optional[str] = None,
        available_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List metadata profiles for all registered models with optional filtering."""
        with self._lock:
            results: List[Dict[str, Any]] = []
            for m_id, meta in self._metadata.items():
                if filter_task and filter_task.lower() not in [t.lower() for t in meta.supported_tasks]:
                    continue
                if filter_category and meta.model_type.lower() != filter_category.lower():
                    continue

                adapter = self._adapters.get(m_id)
                is_avail = adapter.is_available() if adapter else False
                if available_only and not is_avail:
                    continue

                d = meta.to_dict()
                d["is_available"] = is_avail
                d["worker_count"] = len(self._workers.get(m_id, []))
                results.append(d)
            return results

    def get_adapters_for_task(self, task_type: str, available_only: bool = True) -> List[BaseModelAdapter]:
        """Find all registered adapters supporting a given task type."""
        with self._lock:
            matching: List[BaseModelAdapter] = []
            t_clean = task_type.lower().strip()
            for m_id, adapter in self._adapters.items():
                if any(t.lower() == t_clean for t in adapter.task_types):
                    meta = self._metadata.get(m_id)
                    meta_avail = (meta.availability == ModelAvailability.AVAILABLE) if meta else True
                    if not available_only or (adapter.is_available() and meta_avail):
                        matching.append(adapter)
            return matching

    def get_default_for_task(self, task_type: str) -> Optional[BaseModelAdapter]:
        """Find the primary available adapter supporting the given task type."""
        with self._lock:
            t_clean = task_type.lower().strip()
            # Prioritize standard defaults
            if t_clean in ("qa", "extractive_qa"):
                if "grounded-extractive-qa-v1" in self._adapters:
                    ad = self.get_adapter("grounded-extractive-qa-v1")
                    if ad and ad.is_available():
                        return ad
            elif t_clean in ("generative_qa", "summarization", "reasoning"):
                for m_candidate in ("ollama/qwen3.5:2b", "ollama/qwen2.5:1.5b", "smollm2-135m-instruct"):
                    if m_candidate in self._adapters:
                        ad = self.get_adapter(m_candidate)
                        if ad and ad.is_available():
                            return ad
            elif t_clean in ("embedding", "similarity"):
                if "all-minilm-l6-v2" in self._adapters:
                    ad = self.get_adapter("all-minilm-l6-v2")
                    if ad and ad.is_available():
                        return ad

            for adapter in self._adapters.values():
                if any(t.lower() == t_clean for t in adapter.task_types) and adapter.is_available():
                    return adapter
            return None

    def set_availability(self, model_id: str, availability: str) -> bool:
        """Explicitly override model availability status."""
        with self._lock:
            if model_id not in self._metadata:
                return False
            self._metadata[model_id].availability = availability
            return True

    def set_health_status(self, model_id: str, health: str) -> bool:
        """Explicitly override model health status."""
        with self._lock:
            if model_id not in self._metadata:
                return False
            self._metadata[model_id].health_status = health
            return True

    def record_telemetry(
        self,
        model_id: str,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        """Update operational performance telemetry for a model execution."""
        with self._lock:
            if model_id not in self._telemetry:
                self._telemetry[model_id] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "timeout_count": 0,
                    "total_latency_ms": 0.0,
                    "latencies_ms": [],
                    "last_error": None,
                    "last_called_at": 0.0,
                }

            t = self._telemetry[model_id]
            t["total_calls"] += 1
            t["total_latency_ms"] += latency_ms
            t["last_called_at"] = time.time()

            if success:
                t["success_count"] += 1
                t["latencies_ms"].append(latency_ms)
                if len(t["latencies_ms"]) > 100:
                    t["latencies_ms"].pop(0)
            else:
                t["failure_count"] += 1
                t["last_error"] = error
                if error and "timeout" in error.lower():
                    t["timeout_count"] += 1

            # Update ModelMetadata statistics
            if model_id in self._metadata:
                meta = self._metadata[model_id]
                lats = t["latencies_ms"]
                if lats:
                    mean_lat = sum(lats) / len(lats)
                    sorted_lats = sorted(lats)
                    p95_idx = int(0.95 * len(sorted_lats))
                    p95_lat = sorted_lats[min(p95_idx, len(sorted_lats) - 1)]
                    meta.measured_latency = {
                        "mean_ms": round(mean_lat, 2),
                        "p95_ms": round(p95_lat, 2),
                        "last_ms": round(latency_ms, 2),
                        "samples": float(len(lats)),
                        "sample_count": len(lats),
                    }

    def get_telemetry(self, model_id: str) -> Dict[str, Any]:
        """Retrieve execution telemetry for a model."""
        with self._lock:
            return dict(self._telemetry.get(model_id, {}))

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        """Dispatch an inference request through the registered model adapter with full telemetry."""
        target_model_id = request.model_id

        # If 'auto', select the default model for the task
        if target_model_id == "auto" or target_model_id == "default-qa-engine":
            default_adapter = self.get_default_for_task(request.task_type)
            if default_adapter is None:
                return InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=target_model_id,
                    execution_time_ms=0.0,
                    status="REJECTED",
                    error=f"No available model registered for task '{request.task_type}'",
                )
            target_model_id = default_adapter.model_id

        target_worker_id = request.worker_id or request.metadata.get("worker_id")
        adapter = self.get_adapter(target_model_id, worker_id=target_worker_id)
        if adapter is None:
            err_msg = (
                f"Worker '{target_worker_id}' not found for model '{target_model_id}'"
                if target_worker_id
                else f"Model '{target_model_id}' is not registered in the ModelRegistry"
            )
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                model_id=target_model_id,
                execution_time_ms=0.0,
                status="REJECTED",
                error=err_msg,
            )

        # Check availability
        if not adapter.is_available():
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                model_id=target_model_id,
                execution_time_ms=0.0,
                status="REJECTED",
                error=f"Model '{target_model_id}' is currently unavailable",
            )

        # Execute adapter with error handling and telemetry
        start_time = time.perf_counter()
        try:
            response = adapter.execute(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Verify timeout threshold
            max_allowed_ms = request.timeout_ms if request.timeout_ms is not None else (request.timeout * 1000.0)
            if elapsed_ms > max_allowed_ms:
                response = InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=target_model_id,
                    execution_time_ms=round(elapsed_ms, 2),
                    status="TIMEOUT",
                    error=f"Execution ({elapsed_ms:.1f}ms) exceeded timeout limit of {max_allowed_ms:.1f}ms",
                    metadata={"worker_id": adapter.worker_id},
                )

            success = response.status == "SUCCESS"
            self.record_telemetry(
                model_id=target_model_id,
                latency_ms=elapsed_ms,
                success=success,
                error=response.error,
                worker_id=adapter.worker_id,
            )
            return response
        except Exception as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.record_telemetry(
                model_id=target_model_id,
                latency_ms=elapsed_ms,
                success=False,
                error=str(err),
                worker_id=adapter.worker_id,
            )
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                model_id=target_model_id,
                execution_time_ms=round(elapsed_ms, 2),
                status="FAILED",
                error=str(err),
                metadata={"worker_id": adapter.worker_id},
            )

    def reset_registry(self) -> None:
        """Clear all registered adapters and re-initialize defaults (for test isolation)."""
        with self._lock:
            self._adapters.clear()
            self._workers.clear()
            self._metadata.clear()
            self._telemetry.clear()
            self._worker_indices.clear()
            self._register_default_adapters()


# Global singleton instance
_GLOBAL_REGISTRY: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Retrieve the global ModelRegistry singleton."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ModelRegistry()
    return _GLOBAL_REGISTRY
