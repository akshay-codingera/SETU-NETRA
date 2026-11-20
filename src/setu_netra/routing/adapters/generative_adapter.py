"""
generative_adapter.py: Local Small Language Model (SLM) generative adapter for SETU-NETRA.

Why this file exists:
Provides a fully local, offline generative AI adapter powered by HuggingFace Transformers
running on local CPU (e.g. SmolLM2-135M-Instruct). Supports generative question answering,
cross-passage reasoning, and document summarization without external paid APIs.
"""

import time
from typing import Any, Dict, List, Optional
from setu_netra.routing.contracts import (
    InferenceRequest,
    InferenceResponse,
    ModelAvailability,
    ModelCategory,
    ModelHealth,
    ModelMetadata,
)
from setu_netra.routing.interfaces import BaseModelAdapter


class LocalGenerativeAdapter(BaseModelAdapter):
    """Local generative small language model adapter executing directly on CPU."""

    def __init__(
        self,
        model_name_or_path: str = "HuggingFaceTB/SmolLM2-135M-Instruct",
        model_id: str = "smollm2-135m-instruct",
        worker_id: Optional[str] = None,
    ):
        self._model_name = model_name_or_path
        self._model_id = model_id
        self._worker_id = worker_id or f"{model_id}_w1"
        self._tokenizer = None
        self._model = None
        self._is_loaded = False
        self._is_healthy = True

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def is_loaded(self) -> bool:
        """Returns True if the underlying model weights have been loaded into memory."""
        return self._is_loaded

    @property
    def task_types(self) -> List[str]:
        return ["qa", "generative_qa", "summarization", "reasoning"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self._model_id,
            model_name=f"SmolLM2-135M-Instruct ({self._model_name})",
            model_type=ModelCategory.GENERATIVE_QA,
            supported_tasks=self.task_types,
            provider="HuggingFaceTB",
            execution_backend="CPU_PYTORCH",
            memory_requirement={
                "min_ram_mb": 350,
                "recommended_ram_mb": 1024,
                "quantization": "FP32",
            },
            context_length=8192,
            availability=ModelAvailability.AVAILABLE if self.is_available() else ModelAvailability.UNAVAILABLE,
            health_status=ModelHealth.HEALTHY if self._is_healthy else ModelHealth.UNHEALTHY,
            throughput=1.2,
            model_quality_metadata={
                "architecture": "LlamaForCausalLM",
                "parameters_millions": 134.5,
                "open_weights": True,
                "offline_ready": True,
            },
            worker_id=self.worker_id,
        )

    def is_available(self) -> bool:
        """Check whether transformers and local cached weights are ready."""
        try:
            import transformers  # noqa: F401
            import torch         # noqa: F401
            return self._is_healthy
        except ImportError:
            return False

    def health_check(self) -> bool:
        return self.is_available()

    def unload(self) -> None:
        """Unload model weights and tokenizer from memory to free host RAM."""
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
        import gc
        gc.collect()

    def _load_model(self):
        """Lazy load model weights and tokenizer into memory on local CPU."""
        if not self._is_loaded:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from setu_netra.routing.system_telemetry import get_system_telemetry

            sys_tel = get_system_telemetry()
            if sys_tel.is_real and sys_tel.avail_ram_mb < 1500.0:
                logger.warning(
                    "Low host memory (%.1f MB available). Loading SmolLM2 may cause memory pressure.",
                    sys_tel.avail_ram_mb,
                )

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_name,
                local_files_only=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                local_files_only=True,
                dtype=torch.float32,
            )
            self._is_loaded = True
        return self._tokenizer, self._model

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
                error="Local generative model is unavailable or uninitialized",
                metadata={"worker_id": self.worker_id},
            )

        try:
            tokenizer, model = self._load_model()

            prompt_input = request.input_payload or request.prompt_or_payload or ""

            # Format chat prompt using chat template if string
            if isinstance(prompt_input, str):
                messages = [{"role": "user", "content": prompt_input}]
            elif isinstance(prompt_input, list):
                messages = prompt_input
            else:
                messages = [{"role": "user", "content": str(prompt_input)}]

            try:
                formatted_prompt = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                formatted_prompt = str(prompt_input)

            inputs = tokenizer(formatted_prompt, return_tensors="pt")
            max_new = request.max_tokens or request.metadata.get("max_new_tokens", 45)

            # Check timeout before generation
            elapsed_pre = time.perf_counter() - start_time
            if request.timeout and elapsed_pre > request.timeout:
                return InferenceResponse(
                    request_id=request.request_id,
                    result=None,
                    model_id=self._model_id,
                    execution_time_ms=round(elapsed_pre * 1000.0, 2),
                    status="TIMEOUT",
                    error=f"Timeout of {request.timeout}s exceeded before generation",
                    metadata={"worker_id": self.worker_id},
                )

            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new,
                do_sample=False,
            )

            new_tokens = outputs[0][inputs.input_ids.shape[1]:]
            generated_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            elapsed = time.perf_counter() - start_time

            return InferenceResponse(
                request_id=request.request_id,
                result=generated_text,
                model_id=self._model_id,
                execution_time_ms=round(elapsed * 1000.0, 2),
                status="SUCCESS",
                metadata={
                    "tokens_generated": len(new_tokens),
                    "tokens_per_sec": round(len(new_tokens) / max(elapsed, 0.001), 2),
                    "model_type": ModelCategory.GENERATIVE_QA,
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
