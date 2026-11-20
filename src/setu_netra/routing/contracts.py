"""
contracts.py: Unified inference contracts and model metadata for SETU-NETRA Stage 4.

Why this file exists:
Standardizes request and response envelopes, model metadata descriptors, quality profiles,
and operational telemetry across all model categories (OCR, Embedding, Classification,
Extractive QA, Generative QA, Summarization, Reasoning). Serves as the foundation for
adaptive model routing and traffic scheduling.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ModelCategory:
    """Canonical model category classification."""
    OCR = "OCR"
    EMBEDDING = "Embedding"
    CLASSIFICATION = "Classification"
    EXTRACTIVE_QA = "Extractive QA"
    GENERATIVE_QA = "Generative QA"
    GENERATIVE_SLM = "Generative SLM"
    GENERATIVE_CLOUD = "Generative Cloud"
    SUMMARIZATION = "Summarization"
    REASONING = "Reasoning"

    ALL_CATEGORIES = {
        OCR,
        EMBEDDING,
        CLASSIFICATION,
        EXTRACTIVE_QA,
        GENERATIVE_QA,
        GENERATIVE_SLM,
        GENERATIVE_CLOUD,
        SUMMARIZATION,
        REASONING,
    }


class ModelAvailability:
    """Operational availability status of a model or worker."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    LOADING = "LOADING"


class ModelHealth:
    """Health status from active probing."""
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModelMetadata:
    """Centralized descriptor for a model registered in SETU-NETRA."""
    model_id: str
    model_name: str
    model_type: str                            # Must be one of ModelCategory
    supported_tasks: List[str]                 # e.g. ['qa', 'extractive_qa']
    provider: str                              # e.g. 'SETU-NETRA Native', 'HuggingFaceTB'
    execution_backend: str                     # e.g. 'LOCAL_PYTHON', 'CPU_PYTORCH'
    memory_requirement: Dict[str, Any]         # e.g. {'min_ram_mb': 50, 'recommended_ram_mb': 200}
    context_length: int                        # Maximum supported tokens or characters
    availability: str = ModelAvailability.AVAILABLE
    health_status: str = ModelHealth.HEALTHY
    measured_latency: Dict[str, float] = field(default_factory=lambda: {
        "mean_ms": 0.0,
        "p95_ms": 0.0,
        "last_ms": 0.0,
        "samples": 0.0,
    })
    throughput: float = 0.0                    # tokens/sec or items/sec
    model_quality_metadata: Dict[str, Any] = field(default_factory=dict)
    worker_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert descriptor to dictionary format."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "supported_tasks": list(self.supported_tasks),
            "provider": self.provider,
            "execution_backend": self.execution_backend,
            "memory_requirement": dict(self.memory_requirement),
            "context_length": self.context_length,
            "availability": self.availability,
            "health_status": self.health_status,
            "measured_latency": dict(self.measured_latency),
            "throughput": self.throughput,
            "model_quality_metadata": dict(self.model_quality_metadata),
            "worker_id": self.worker_id,
            "created_at": self.created_at,
        }


@dataclass
class InferenceRequest:
    """Standardized input envelope for all inference execution adapters."""
    input_payload: Any = None                  # Core input: text prompt, list of texts, image path, etc.
    task_type: str = "qa"                      # 'qa', 'extractive_qa', 'generative_qa', 'embedding', 'ocr', 'classification', 'summarization', 'reasoning'
    model_id: str = "default-qa-engine"        # Specific model ID or 'auto'
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 1                          # 1 (Highest interactive) to 5 (Background batch)
    timeout: float = 30.0                      # Timeout in seconds
    max_tokens: Optional[int] = None           # Optional output length constraint
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    prompt_or_payload: Any = None              # Backward-compatible alias for input_payload
    context: Optional[str] = None              # Optional context text or evidence passage
    timeout_ms: Optional[float] = None         # Optional timeout in milliseconds
    worker_id: Optional[str] = None            # Optional target worker ID

    def __post_init__(self):
        # Bi-directional sync between input_payload and prompt_or_payload
        if self.input_payload is None and self.prompt_or_payload is not None:
            self.input_payload = self.prompt_or_payload
        elif self.prompt_or_payload is None and self.input_payload is not None:
            self.prompt_or_payload = self.input_payload

        # Synchronize context with metadata
        if self.context is not None and "context" not in self.metadata:
            self.metadata["context"] = self.context
        elif self.context is None and "context" in self.metadata:
            self.context = str(self.metadata["context"])

        # Synchronize timeout and timeout_ms
        if self.timeout_ms is not None:
            self.timeout = float(self.timeout_ms) / 1000.0
        else:
            self.timeout_ms = float(self.timeout) * 1000.0

        # Synchronize worker_id with metadata
        if self.worker_id is not None and "worker_id" not in self.metadata:
            self.metadata["worker_id"] = self.worker_id
        elif self.worker_id is None and "worker_id" in self.metadata:
            self.worker_id = str(self.metadata["worker_id"])

        # Synchronize max_tokens with metadata if present
        if self.max_tokens is not None and "max_tokens" not in self.metadata:
            self.metadata["max_tokens"] = self.max_tokens
        elif self.max_tokens is None and "max_tokens" in self.metadata:
            try:
                self.max_tokens = int(self.metadata["max_tokens"])
            except (ValueError, TypeError):
                pass


@dataclass
class InferenceResponse:
    """Standardized output envelope returned from all inference execution adapters."""
    request_id: str
    result: Any
    model_id: str = "unknown-model"
    execution_time_ms: float = 0.0             # Latency in milliseconds
    status: str = "SUCCESS"                    # 'SUCCESS', 'FAILED', 'TIMEOUT', 'REJECTED'
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    executing_model_id: Optional[str] = None   # Backward-compatible alias for model_id
    execution_time: Optional[float] = None     # Backward-compatible alias in seconds
    error_info: Optional[str] = None           # Backward-compatible alias for error

    def __post_init__(self):
        # Bi-directional sync between model_id and executing_model_id
        if self.executing_model_id is not None and self.model_id == "unknown-model":
            self.model_id = self.executing_model_id
        elif self.executing_model_id is None:
            self.executing_model_id = self.model_id

        # Bi-directional sync between execution_time_ms and execution_time (seconds)
        if self.execution_time is not None and self.execution_time_ms == 0.0:
            self.execution_time_ms = round(self.execution_time * 1000.0, 2)
        elif self.execution_time is None:
            self.execution_time = round(self.execution_time_ms / 1000.0, 4)

        # Bi-directional sync between error and error_info
        if self.error_info is not None and self.error is None:
            self.error = self.error_info
        elif self.error is not None and self.error_info is None:
            self.error_info = self.error


class WorkerState:
    """Operational state of an inference worker thread."""
    IDLE = "IDLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    COOLING_DOWN = "COOLING_DOWN"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class QualityRequirement:
    """Requested response precision/fidelity profile."""
    HIGH_PRECISION = "HIGH_PRECISION"      # Zero hallucination, strict evidence matching
    BALANCED = "BALANCED"                  # Grounded with synthesis capability
    CREATIVE_SYNTHESIS = "CREATIVE_SYNTHESIS"  # Generative reasoning/paraphrase allowed


class EvidenceRequirement:
    """Evidence grounding requirement for question answering."""
    REQUIRE_VERIFIED_CITATIONS = "REQUIRE_VERIFIED_CITATIONS"  # Exact source citation mandatory
    SYNTHESIS_ALLOWED = "SYNTHESIS_ALLOWED"                    # General reasoning with context allowed
    NO_EVIDENCE_NEEDED = "NO_EVIDENCE_NEEDED"                  # Open general-knowledge or classification


@dataclass
class RoutingDecision:
    """Structured decision produced by the AdaptiveModelRouter."""
    selected_model_id: Optional[str]
    task_type: str
    confidence: float
    reason: str
    fallback_model_id: Optional[str] = None
    status: str = "ROUTED"                 # 'ROUTED', 'REJECTED', 'FALLBACK'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulingDecision:
    """Structured decision produced by worker schedulers."""
    selected_worker_id: Optional[str]
    model_id: str
    estimated_latency_ms: float = 0.0
    queue_wait_ms: float = 0.0
    strategy: str = "ROUND_ROBIN"
    reason: str = ""
    status: str = "SCHEDULED"              # 'SCHEDULED', 'REJECTED', 'QUEUED'
    metadata: Dict[str, Any] = field(default_factory=dict)

