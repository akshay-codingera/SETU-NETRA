"""
classifier_adapter.py: Unified classification adapter for SETU-NETRA.

Why this file exists:
Wraps academic domain classifiers and cognitive intent classifiers behind the
unified InferenceRequest / InferenceResponse interface contract.
"""

import time
from typing import Any, Dict, List, Optional
from setu_netra.qa.question_extractor import classify_question_intent
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.semantic.domain.classifier import OpenVocabularyDomainClassifier
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine


class ClassificationExecutionAdapter(BaseModelAdapter):
    """Adapter exposing document domain and cognitive intent classification."""

    def __init__(
        self,
        classifier: Optional[OpenVocabularyDomainClassifier] = None,
        model_id: str = "academic-domain-classifier-v1",
        worker_id: Optional[str] = None,
    ):
        if classifier is None:
            engine = OfflineSemanticEngine()
            self._classifier = OpenVocabularyDomainClassifier(embedding_engine=engine)
        else:
            self._classifier = classifier
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
        return ["classification", "domain_detection", "intent_classification"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name="Academic Domain & Cognitive Intent Classifier",
            model_type=ModelCategory.CLASSIFICATION,
            supported_tasks=self.task_types,
            provider="SETU-NETRA Native",
            execution_backend="LOCAL_PYTHON",
            memory_requirement={
                "min_ram_mb": 30,
                "recommended_ram_mb": 60,
                "quantization": "None",
            },
            context_length=2048,
            availability=ModelAvailability.AVAILABLE if self.is_available() else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self._is_healthy else ModelHealth.UNHEALTHY,
            throughput=200.0,
            model_quality_metadata={
                "domains_supported": 5,
                "intents_supported": 6,
            },
            worker_id=self.worker_id,
        )

    def is_available(self) -> bool:
        return self._is_healthy

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
                error="Classifier adapter is unavailable",
                metadata={"worker_id": self.worker_id},
            )

        try:
            payload = str(request.input_payload or request.prompt_or_payload or "")
            task = request.task_type.lower()

            if "intent" in task:
                is_mcq = request.metadata.get("is_mcq", False)
                intent = classify_question_intent(payload, is_mcq=is_mcq)
                result_data = {
                    "task": "intent_classification",
                    "intent": intent,
                    "prompt": payload,
                }
            else:
                candidates, status, warnings = self._classifier.classify(payload)
                top_domain = candidates[0].domain_name if candidates else "UNKNOWN"
                confidence = round(float(candidates[0].similarity_score), 4) if candidates else 0.0
                result_data = {
                    "task": "domain_classification",
                    "status": status,
                    "top_domain": top_domain,
                    "confidence": confidence,
                    "warnings": warnings,
                    "all_candidates": [
                        {
                            "domain_id": c.domain_id,
                            "domain_name": c.domain_name,
                            "confidence": round(float(c.similarity_score), 4),
                            "evidence_terms": list(c.evidence_terms),
                        }
                        for c in candidates
                    ],
                }

            elapsed = time.perf_counter() - start_time
            return InferenceResponse(
                request_id=request.request_id,
                result=result_data,
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="SUCCESS",
                metadata={"worker_id": self.worker_id},
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
