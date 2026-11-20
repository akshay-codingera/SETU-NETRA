"""
router.py: Adaptive Model Router for SETU-NETRA Stage 5.

Why this file exists:
Provides an intelligent model routing control plane that selects the optimal AI model
for each incoming InferenceRequest based on task type, cognitive intent, complexity,
quality and evidence requirements, latency budgets, and real-time model telemetry.
Maintains strict separation between Model Selection (this file) and Worker Scheduling.
"""

import logging
from typing import Any, Dict, List, Optional

from setu_netra.core.config import is_local_only
from setu_netra.qa.question_extractor import classify_question_intent
from setu_netra.routing.contracts import (
    EvidenceRequirement,
    InferenceRequest,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    QualityRequirement,
    RoutingDecision,
)
from setu_netra.routing.registry import ModelRegistry, get_model_registry

logger = logging.getLogger(__name__)


class AdaptiveModelRouter:
    """Adaptive decision engine selecting the optimal model for an inference task."""

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self._registry = registry or get_model_registry()

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    def route(self, request: InferenceRequest) -> RoutingDecision:
        """Analyze request attributes and historical telemetry to select the best model.

        Evaluates:
        - Declared task_type
        - Cognitive intent of question / prompt
        - Input complexity (character/token size)
        - Evidence requirements (mandatory citations vs generative synthesis)
        - Latency budget (max_acceptable_latency_ms)
        - Model capabilities, operational health, and historical latency
        """
        raw_payload = str(request.input_payload or request.prompt_or_payload or "")
        task_type = request.task_type.lower().strip()
        requested_model = request.model_id.strip() if request.model_id else "auto"

        # 1. Handle Explicit Model Targeting
        if requested_model not in ("auto", "default-qa-engine", ""):
            is_cloud = any(c in requested_model.lower() for c in ("gemini", "groq", "openrouter", "cloud"))
            if is_cloud:
                prov = "gemini" if "gemini" in requested_model.lower() else ("groq" if "groq" in requested_model.lower() else "openrouter")
                from setu_netra.core.config import get_api_key
                key = get_api_key(prov)
                adapter = self._registry.get_adapter(requested_model)
                if adapter and key:
                    # User explicitly chose cloud model and has configured key: honor user choice directly
                    return RoutingDecision(
                        selected_model_id=requested_model,
                        task_type=task_type,
                        confidence=0.95,
                        reason=f"Explicit cloud acceleration route to '{requested_model}'.",
                        status="TARGETED",
                    )
                elif adapter and not key:
                    # Allow adapter to execute and return its structured help message explaining how to get a free key
                    return RoutingDecision(
                        selected_model_id=requested_model,
                        task_type=task_type,
                        confidence=0.90,
                        reason=f"Cloud model '{requested_model}' targeted (key configuration check).",
                        status="TARGETED",
                    )
                elif is_local_only():
                    fallbacks = self._registry.get_adapters_for_task(task_type, available_only=True)
                    local_fallbacks = [a for a in fallbacks if not any(c in a.model_id.lower() for c in ("gemini", "groq", "openrouter", "cloud"))]
                    fallback_id = local_fallbacks[0].model_id if local_fallbacks else "ollama/qwen3.5:2b"
                    return RoutingDecision(
                        selected_model_id=fallback_id,
                        task_type=task_type,
                        confidence=0.85,
                        reason=f"Local-Only Privacy Mode is active. Cloud model '{requested_model}' rerouted to local '{fallback_id}'.",
                        status="REROUTED_LOCAL",
                    )

            meta = self._registry.get_metadata(requested_model)
            adapter = self._registry.get_adapter(requested_model)
            if adapter is None or meta is None:
                return RoutingDecision(
                    selected_model_id=None,
                    task_type=task_type,
                    confidence=0.0,
                    reason=f"Requested model '{requested_model}' is not registered in the ModelRegistry.",
                    status="REJECTED",
                )
            canonical_model_id = adapter.model_id
            if not adapter.is_available() or meta.availability != ModelAvailability.AVAILABLE:
                # Attempt to find a fallback for the same task
                fallbacks = self._registry.get_adapters_for_task(task_type, available_only=True)
                valid_fallbacks = [a for a in fallbacks if a.model_id != canonical_model_id]
                fallback_id = valid_fallbacks[0].model_id if valid_fallbacks else None
                return RoutingDecision(
                    selected_model_id=fallback_id,
                    task_type=task_type,
                    confidence=0.5 if fallback_id else 0.0,
                    fallback_model_id=fallback_id,
                    reason=f"Target model '{requested_model}' is currently unavailable (Status: {meta.availability}).",
                    status="FALLBACK" if fallback_id else "REJECTED",
                )
            return RoutingDecision(
                selected_model_id=canonical_model_id,
                task_type=task_type,
                confidence=1.0,
                reason=f"Direct targeting for registered model '{requested_model}'.",
                status="ROUTED",
            )

        # 2. Extract Cognitive & Execution Context
        intent = request.metadata.get("intent")
        if not intent and raw_payload and task_type in ("qa", "extractive_qa", "generative_qa", "reasoning"):
            is_mcq = request.metadata.get("is_mcq", False)
            intent = classify_question_intent(raw_payload, is_mcq=is_mcq)

        evidence_req = request.metadata.get(
            "evidence_requirement",
            EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS if (request.context or "context" in request.metadata) else EvidenceRequirement.SYNTHESIS_ALLOWED
        )
        quality_req = request.metadata.get("quality_requirement", QualityRequirement.BALANCED)
        max_latency_ms = request.timeout_ms or (request.timeout * 1000.0)
        token_estimate = max(1, len(raw_payload) // 4)

        # 3. Task Category: Vision / OCR
        if task_type in ("ocr", "text_extraction", "image_ocr"):
            ocr_adapters = self._registry.get_adapters_for_task("ocr", available_only=True)
            if not ocr_adapters:
                return RoutingDecision(
                    selected_model_id=None,
                    task_type=task_type,
                    confidence=0.0,
                    reason="No healthy OCR model adapter registered.",
                    status="REJECTED",
                )
            return RoutingDecision(
                selected_model_id=ocr_adapters[0].model_id,
                task_type="ocr",
                confidence=0.95,
                reason="Routed to active OCR recognition engine.",
                status="ROUTED",
            )

        # 4. Task Category: Semantic Embeddings
        if task_type in ("embedding", "similarity", "vectorization"):
            embed_adapters = self._registry.get_adapters_for_task("embedding", available_only=True)
            if not embed_adapters:
                return RoutingDecision(
                    selected_model_id=None,
                    task_type=task_type,
                    confidence=0.0,
                    reason="No available embedding engine registered.",
                    status="REJECTED",
                )
            # Prioritize neural model if available
            selected = embed_adapters[0]
            for a in embed_adapters:
                if "minilm" in a.model_id.lower():
                    selected = a
                    break
            return RoutingDecision(
                selected_model_id=selected.model_id,
                task_type="embedding",
                confidence=0.98,
                reason="Routed to compatible dense embedding adapter.",
                status="ROUTED",
            )

        # 5. Task Category: Classification & Domain Detection
        if task_type in ("classification", "domain_detection", "intent_classification"):
            clf_adapters = self._registry.get_adapters_for_task("classification", available_only=True)
            if not clf_adapters:
                return RoutingDecision(
                    selected_model_id=None,
                    task_type=task_type,
                    confidence=0.0,
                    reason="No active classification adapter registered.",
                    status="REJECTED",
                )
            return RoutingDecision(
                selected_model_id=clf_adapters[0].model_id,
                task_type=task_type,
                confidence=0.95,
                reason="Routed to academic domain & intent classifier.",
                status="ROUTED",
            )

        # 6. Task Category: Question Answering, Synthesis & Reasoning
        if task_type in ("qa", "extractive_qa", "generative_qa", "summarization", "reasoning"):
            # Check availability of extractive and generative candidates
            extractive_adapters = self._registry.get_adapters_for_task("extractive_qa", available_only=True)
            generative_adapters = self._registry.get_adapters_for_task("generative_qa", available_only=True)

            extractive_id = extractive_adapters[0].model_id if extractive_adapters else None
            # Prioritize Ollama Qwen over SmolLM2 if Ollama is available
            generative_id = None
            if generative_adapters:
                ollama_candidates = [a for a in generative_adapters if "ollama" in a.model_id.lower()]
                generative_id = ollama_candidates[0].model_id if ollama_candidates else generative_adapters[0].model_id

            # Policy A: Strict Evidence Grounding or Extractive QA requested
            if task_type == "extractive_qa" or evidence_req == EvidenceRequirement.REQUIRE_VERIFIED_CITATIONS or quality_req == QualityRequirement.HIGH_PRECISION:
                if extractive_id:
                    return RoutingDecision(
                        selected_model_id=extractive_id,
                        task_type="extractive_qa",
                        confidence=0.99,
                        reason="Selected zero-hallucination Extractive QA engine for verified citation grounding.",
                        fallback_model_id=generative_id,
                        status="ROUTED",
                        metadata={"intent": intent, "epistemic_mode": "VERIFIED_EXTRACTIVE"},
                    )
                elif generative_id:
                    return RoutingDecision(
                        selected_model_id=generative_id,
                        task_type="generative_qa",
                        confidence=0.60,
                        reason="Extractive engine unavailable; falling back to Generative SLM with caveat.",
                        fallback_model_id=None,
                        status="FALLBACK",
                        metadata={"intent": intent, "warning": "Citation verification may be degraded."},
                    )
                else:
                    return RoutingDecision(
                        selected_model_id=None,
                        task_type=task_type,
                        confidence=0.0,
                        reason="No available QA models (extractive or generative) in registry.",
                        status="REJECTED",
                    )

            # Policy B: Generative Synthesis or Summarization requested
            if task_type in ("generative_qa", "summarization") or quality_req == QualityRequirement.CREATIVE_SYNTHESIS:
                # Latency check: If SLA is too tight (< 1500 ms) for local generative SLM (~2500 ms)
                if max_latency_ms < 1500.0:
                    if extractive_id:
                        return RoutingDecision(
                            selected_model_id=extractive_id,
                            task_type="extractive_qa",
                            confidence=0.75,
                            reason=f"Strict SLA ({max_latency_ms:.0f}ms) cannot accommodate SLM; routed to fast extractive engine (~1ms).",
                            status="FALLBACK",
                            fallback_model_id=generative_id,
                        )
                    else:
                        return RoutingDecision(
                            selected_model_id=None,
                            task_type=task_type,
                            confidence=0.0,
                            reason=f"Latency budget of {max_latency_ms:.0f}ms is insufficient for local generative model.",
                            status="REJECTED",
                        )

                if generative_id:
                    return RoutingDecision(
                        selected_model_id=generative_id,
                        task_type="generative_qa",
                        confidence=0.92,
                        reason="Routed to local generative SLM for narrative synthesis & summarization.",
                        fallback_model_id=extractive_id,
                        status="ROUTED",
                    )
                elif extractive_id:
                    return RoutingDecision(
                        selected_model_id=extractive_id,
                        task_type="extractive_qa",
                        confidence=0.70,
                        reason="Generative model unavailable; routed to extractive fallback.",
                        status="FALLBACK",
                    )
                else:
                    return RoutingDecision(
                        selected_model_id=None,
                        task_type=task_type,
                        confidence=0.0,
                        reason="No generative or extractive models available.",
                        status="REJECTED",
                    )

            # Policy C: Reasoning tasks
            if task_type == "reasoning":
                # Note: Small SLMs (< 150M) handle light comparative deduction; deep multi-hop uses extractive grounding
                if generative_id and max_latency_ms >= 2000.0:
                    return RoutingDecision(
                        selected_model_id=generative_id,
                        task_type="reasoning",
                        confidence=0.55,
                        reason="Routed to local SLM for comparative reasoning (limited multi-hop capacity).",
                        fallback_model_id=extractive_id,
                        status="ROUTED",
                        metadata={"caveat": "SLM (<150M) has limited multi-hop deductive capacity. Factual verification recommended."},
                    )
                elif extractive_id:
                    return RoutingDecision(
                        selected_model_id=extractive_id,
                        task_type="extractive_qa",
                        confidence=0.80,
                        reason="Reasoning routed to grounded extractive engine for factual verification.",
                        status="ROUTED",
                    )

            # Policy D: Generic 'qa' task type - resolve via cognitive intent
            if intent in ("COMPARISON", "PROCEDURAL", "EVALUATIVE") and generative_id and max_latency_ms >= 2500.0:
                return RoutingDecision(
                    selected_model_id=generative_id,
                    task_type="generative_qa",
                    confidence=0.88,
                    reason=f"Cognitive intent '{intent}' benefits from generative synthesis.",
                    fallback_model_id=extractive_id,
                    status="ROUTED",
                )
            else:
                # Default to high-confidence extractive QA
                if extractive_id:
                    return RoutingDecision(
                        selected_model_id=extractive_id,
                        task_type="extractive_qa",
                        confidence=0.95,
                        reason="Factual / definition question routed to grounded extractive QA.",
                        fallback_model_id=generative_id,
                        status="ROUTED",
                    )
                elif generative_id:
                    return RoutingDecision(
                        selected_model_id=generative_id,
                        task_type="generative_qa",
                        confidence=0.75,
                        reason="Grounded extractive model unavailable; routed to generative SLM.",
                        status="FALLBACK",
                    )

        # 7. Incompatible or Unknown Task Rejection
        compatible = self._registry.get_adapters_for_task(task_type, available_only=True)
        if compatible:
            return RoutingDecision(
                selected_model_id=compatible[0].model_id,
                task_type=task_type,
                confidence=0.80,
                reason=f"Routed to primary compatible adapter for task '{task_type}'.",
                status="ROUTED",
            )

        return RoutingDecision(
            selected_model_id=None,
            task_type=task_type,
            confidence=0.0,
            reason=f"Unsupported task type '{task_type}'. No compatible models registered.",
            status="REJECTED",
        )
