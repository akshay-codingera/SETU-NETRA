# SETU-NETRA Unified Inference Interface Specification
## Technical Specification of Input/Output Envelopes and Adapter Protocols

**Document Reference**: SPEC-STAGE4-INF-001  
**Project**: SETU-NETRA (Bridge-Eye)  
**Date**: November 2026  
**Status**: APPROVED & IMPLEMENTED  

---

## 1. Scope & Design Philosophy

The **Unified Inference Interface** establishes a model-agnostic, task-independent protocol for all neural and algorithmic components in SETU-NETRA. 

Traditional AI pipelines often suffer from tight coupling, where changing an embedding model, OCR engine, or language model breaks downstream calling code due to differing input signatures, tensor formats, or error handling. 

SETU-NETRA resolves this by requiring every model execution to accept a single envelope (`InferenceRequest`) and return a single envelope (`InferenceResponse`).

---

## 2. Protocol Envelopes

### 2.1 `InferenceRequest` Data Contract

```python
@dataclass
class InferenceRequest:
    input_payload: Any = None                  # Core input: text prompt, list of texts, image path, etc.
    task_type: str = "qa"                      # 'qa', 'extractive_qa', 'generative_qa', 'embedding', 'ocr', 'classification', 'summarization', 'reasoning'
    model_id: str = "default-qa-engine"        # Specific model ID or 'auto'
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 1                          # 1 (Highest interactive) to 5 (Background batch)
    timeout: float = 30.0                      # Timeout in seconds
    timeout_ms: Optional[float] = None         # Timeout in milliseconds
    context: Optional[str] = None              # Optional context text or evidence passage
    worker_id: Optional[str] = None            # Optional target worker ID
    max_tokens: Optional[int] = None           # Optional output length constraint
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    prompt_or_payload: Any = None              # Backward-compatible alias for input_payload
```

#### Field Specifications:
- `input_payload`: Primary data payload. May be a `str` (question, text query), `List[str]` (batch of sentences for embeddings), `Path` / `str` (path to an image for OCR), or dictionary.
- `task_type`: Categorical task identifier. Drives dynamic model discovery when `model_id='auto'`.
- `model_id`: Unique ID of the desired model. If set to `"auto"` or `"default-qa-engine"`, the Model Registry dynamically selects the best available adapter registered for the specified `task_type`.
- `request_id`: Standardized UUID4 string for distributed tracing and logging.
- `timeout` / `timeout_ms`: Maximum execution duration before the registry halts the operation.
- `context`: Explicit passage text provided as evidence grounding for question answering.
- `worker_id`: Optional pin to direct execution to a specific worker instance.
- `metadata`: Flexible dictionary for ancillary parameters (e.g., `temperature`, `is_mcq`, `do_sample`).

---

### 2.2 `InferenceResponse` Data Contract

```python
@dataclass
class InferenceResponse:
    request_id: str                            # Mirrored request UUID
    result: Any                                # Output prediction, text, vector, or structure
    model_id: str = "unknown-model"            # Executing model ID
    execution_time_ms: float = 0.0             # Latency in milliseconds
    status: str = "SUCCESS"                    # 'SUCCESS', 'FAILED', 'TIMEOUT', 'REJECTED'
    error: Optional[str] = None                # Diagnostic error message
    metadata: Dict[str, Any] = field(default_factory=dict)
    executing_model_id: Optional[str] = None   # Backward-compatible alias for model_id
    execution_time: Optional[float] = None     # Backward-compatible alias in seconds
    error_info: Optional[str] = None           # Backward-compatible alias for error
```

#### Execution Statuses:
- **`SUCCESS`**: Model completed execution normally. `result` contains valid output.
- **`FAILED`**: Model adapter threw an unhandled exception or failed inference. `error` contains diagnostic traceback.
- **`TIMEOUT`**: Execution duration exceeded the requested `timeout` threshold.
- **`REJECTED`**: Model was not registered, had no available workers, or failed health check.

---

## 3. Bidirectional Backward Compatibility

Stage 4 guarantees **100% backward compatibility** with code written during Stage 3 or earlier sprints.

The dataclasses use custom `__post_init__` hooks to ensure transparent bidirectional synchronization:

```mermaid
graph LR
    subgraph InferenceRequest Sync
        A[prompt_or_payload (Stage 3)] <--> B[input_payload (Stage 4)]
        C[timeout in seconds] <--> D[timeout_ms in milliseconds]
        E[context parameter] <--> F[metadata['context']]
    end
    subgraph InferenceResponse Sync
        G[executing_model_id (Stage 3)] <--> H[model_id (Stage 4)]
        I[execution_time in seconds] <--> J[execution_time_ms in ms]
        K[error_info (Stage 3)] <--> L[error (Stage 4)]
    end
```

Any component reading or writing the older Stage 3 attributes continues to function without modification.

---

## 4. Standardized Task Payload Formats

| Task Type | `InferenceRequest.input_payload` | `InferenceResponse.result` | `InferenceResponse.metadata` |
| :--- | :--- | :--- | :--- |
| `extractive_qa` | Question `str`, with `context=...` | Answer `str` with citation tag | `epistemic_status`, `citations` list, `worker_id` |
| `generative_qa` | Prompt `str`, optional `context=...` | Generated answer `str` | `tokens_generated`, `tokens_per_sec`, `worker_id` |
| `embedding` | Single `str` or `List[str]` | `List[List[float]]` (dense vectors) | `dimension`, `batch_size`, `worker_id` |
| `ocr` | Image path (`Path` or `str`) or `PIL.Image` | `List[Dict]` (OCR bounding boxes and text) | `box_count`, `mean_confidence`, `worker_id` |
| `classification` | Text snippet `str` | `Dict` (`top_domain`, `confidence`, `all_candidates`) | `worker_id` |
| `intent_classification` | Question query `str` | `Dict` (`task`, `intent`, `prompt`) | `worker_id` |
| `summarization` | Document text `str` | Summary text `str` | `tokens_generated`, `compression_ratio` |
| `reasoning` | Premise and question `str` | Deductive answer `str` | `reasoning_steps`, `tokens_generated` |

---

## 5. Adapter Implementation Guide (`BaseModelAdapter`)

All new model adapters must inherit from `BaseModelAdapter`:

```python
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse, ModelMetadata

class CustomModelAdapter(BaseModelAdapter):
    @property
    def model_id(self) -> str:
        return "my-custom-model-v1"

    @property
    def worker_id(self) -> str:
        return "my-custom-model-v1_w1"

    @property
    def task_types(self) -> List[str]:
        return ["generative_qa", "summarization"]

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(...)

    def is_available(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def execute(self, request: InferenceRequest) -> InferenceResponse:
        # Implementation logic...
        return InferenceResponse(...)
```
