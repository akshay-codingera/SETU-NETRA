"""
routing: Adaptive model routing and unified inference registry for SETU-NETRA.
"""

from setu_netra.routing.contracts import (
    EvidenceRequirement,
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
    QualityRequirement,
    RoutingDecision,
    SchedulingDecision,
    WorkerState,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.registry import ModelRegistry, get_model_registry
from setu_netra.routing.router import AdaptiveModelRouter
from setu_netra.routing.worker_pool import InferenceWorker, InferenceWorkerPool
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.system_telemetry import SystemTelemetry, get_system_telemetry
from setu_netra.routing.schedulers import (
    BaseScheduler,
    RoundRobinScheduler,
    RandomScheduler,
    LeastOutstandingRequestsScheduler,
    ShortestEstimatedCompletionTimeScheduler,
    CapacityAwareScheduler,
    AdaptiveResilientScheduler,
)

__all__ = [
    "InferenceRequest",
    "InferenceResponse",
    "ModelCategory",
    "ModelAvailability",
    "ModelHealth",
    "ModelMetadata",
    "WorkerState",
    "QualityRequirement",
    "EvidenceRequirement",
    "RoutingDecision",
    "SchedulingDecision",
    "BaseModelAdapter",
    "ModelRegistry",
    "get_model_registry",
    "AdaptiveModelRouter",
    "InferenceWorker",
    "InferenceWorkerPool",
    "IntelligentInferencePipeline",
    "SystemTelemetry",
    "get_system_telemetry",
    "BaseScheduler",
    "RoundRobinScheduler",
    "RandomScheduler",
    "LeastOutstandingRequestsScheduler",
    "ShortestEstimatedCompletionTimeScheduler",
    "CapacityAwareScheduler",
    "AdaptiveResilientScheduler",
]
