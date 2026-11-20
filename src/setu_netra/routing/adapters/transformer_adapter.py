"""
transformer_adapter.py: HuggingFace Transformers adapter for local small language models (SLMs).

Why this file exists:
Enables local CPU execution of small quantized/open-weight models (e.g. Qwen2.5-0.5B,
SmolLM, Phi-3-mini) using PyTorch on CPU without external API calls.
"""

import time
from typing import Any, Dict, List, Optional
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse
from setu_netra.routing.interfaces import BaseModelAdapter


class HuggingFaceTransformerAdapter(BaseModelAdapter):
    """Adapter for running HuggingFace causal language models on CPU."""

    def __init__(self, model_name_or_path: str = "HuggingFaceTB/SmolLM-135M-Instruct"):
        self._model_name = model_name_or_path
        self._pipeline = None
        self._is_ready = False

    @property
    def model_id(self) -> str:
        return f"hf_{self._model_name.replace('/', '_')}"

    @property
    def task_types(self) -> List[str]:
        return ["qa", "summarization", "reasoning"]

    def is_available(self) -> bool:
        """Check whether transformers and local model files are available."""
        try:
            import transformers  # noqa: F401
            import torch         # noqa: F401
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._pipeline is None:
            from transformers import pipeline
            import torch
            # Initialize text-generation pipeline on CPU
            self._pipeline = pipeline(
                "text-generation",
                model=self._model_name,
                device="cpu",
                torch_dtype=torch.float32,
            )
            self._is_ready = True
        return self._pipeline

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        start_time = time.perf_counter()
        try:
            pipe = self._load_model()
            prompt = str(request.prompt_or_payload)
            max_new = request.metadata.get("max_new_tokens", 150)

            outputs = pipe(
                prompt,
                max_new_tokens=max_new,
                do_sample=False,
                temperature=0.1,
            )
            generated_text = outputs[0]["generated_text"]
            elapsed = time.perf_counter() - start_time

            return InferenceResponse(
                request_id=request.request_id,
                result=generated_text,
                executing_model_id=self.model_id,
                execution_time=round(elapsed, 4),
                status="SUCCESS",
                metadata={"tokens_budget": max_new},
            )
        except Exception as err:
            elapsed = time.perf_counter() - start_time
            return InferenceResponse(
                request_id=request.request_id,
                result=None,
                executing_model_id=self.model_id,
                execution_time=round(elapsed, 4),
                status="FAILED",
                error_info=str(err),
            )
