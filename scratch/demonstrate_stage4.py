"""
demonstrate_stage4.py: Live demonstration of Stage 4 Model Registry and Unified Inference Interface.

Demonstrates:
1. Thread-safe Model Registry with multi-category model catalog.
2. Unified interface dispatching to Grounded Extractive QA and SmolLM2 Generative QA.
3. Telemetry tracking (latency, sample counts, P95 metrics) across distinct execution backends.
"""

import sys
import time
from pathlib import Path

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.contracts import InferenceRequest, ModelCategory
from setu_netra.routing.registry import ModelRegistry


def run_demonstration():
    print("=" * 80)
    print("SETU-NETRA STAGE 4: MODEL REGISTRY & UNIFIED INFERENCE INTERFACE DEMO")
    print("=" * 80)

    # 1. Initialize Registry
    registry = ModelRegistry(register_defaults=True)
    registered_ids = registry.get_registered_model_ids()
    print(f"\n[1] Centralized Model Registry initialized with {len(registered_ids)} default models:")
    for m_id in registered_ids:
        meta = registry.get_model_metadata(m_id)
        print(f"  * {m_id:30s} | Category: {meta.model_type:15s} | Backend: {meta.execution_backend:12s} | RAM: {meta.memory_requirement.get('min_ram_mb', 0)}MB")

    # 2. Invoke Model 1: Grounded Extractive QA
    print("\n" + "-" * 80)
    print("[2] Invoking Model 1: Grounded Extractive QA (Native CPU, 0 MB download)")
    print("-" * 80)
    req1 = InferenceRequest(
        task_type="extractive_qa",
        model_id="grounded-extractive-qa-v1",
        input_payload="What is the operating frequency of the sensor?",
        context="The optical sensor operates at a frequency of 144 Hz with ultra-low latency [Doc: sensor_spec.pdf, Page: 2, Block: 4].",
    )
    res1 = registry.execute(req1)
    print(f"Request ID:         {res1.request_id}")
    print(f"Status:             {res1.status}")
    print(f"Executing Model:    {res1.model_id}")
    print(f"Latency:            {res1.execution_time_ms} ms")
    print(f"Result / Answer:    {res1.result}")
    print(f"Epistemic Status:   {res1.metadata.get('epistemic_status')}")
    print(f"Citations:          {res1.metadata.get('citations')}")

    # 3. Invoke Model 2: Academic Domain Classifier
    print("\n" + "-" * 80)
    print("[3] Invoking Model 2: Academic Domain & Intent Classifier")
    print("-" * 80)
    req2 = InferenceRequest(
        task_type="domain_detection",
        model_id="academic-domain-classifier-v1",
        input_payload="Eigenvalue decomposition and orthogonal projections in Hilbert spaces.",
    )
    res2 = registry.execute(req2)
    print(f"Request ID:         {res2.request_id}")
    print(f"Status:             {res2.status}")
    print(f"Executing Model:    {res2.model_id}")
    print(f"Latency:            {res2.execution_time_ms} ms")
    print(f"Top Domain:         {res2.result.get('top_domain')}")
    print(f"Confidence:         {res2.result.get('confidence')}")

    # 4. Invoke Model 3: Local Generative SLM (SmolLM2-135M-Instruct)
    print("\n" + "-" * 80)
    print("[4] Invoking Model 3: Local Generative SLM (SmolLM2-135M-Instruct on CPU)")
    print("-" * 80)
    req3 = InferenceRequest(
        task_type="generative_qa",
        model_id="smollm2-135m-instruct",
        input_payload="Explain the difference between deadlock prevention and deadlock avoidance in one sentence.",
        max_tokens=40,
    )
    print("Executing generative inference on CPU...")
    res3 = registry.execute(req3)
    print(f"Request ID:         {res3.request_id}")
    print(f"Status:             {res3.status}")
    print(f"Executing Model:    {res3.model_id}")
    print(f"Latency:            {res3.execution_time_ms} ms")
    print(f"Result / Text:      {res3.result}")
    print(f"Tokens Generated:   {res3.metadata.get('tokens_generated')}")
    print(f"Generation Speed:   {res3.metadata.get('tokens_per_sec')} tokens/s")

    # 5. Check Registry Telemetry
    print("\n" + "-" * 80)
    print("[5] Registry Telemetry & Health Verification")
    print("-" * 80)
    for m_id in [res1.model_id, res2.model_id, res3.model_id]:
        meta = registry.get_model_metadata(m_id)
        lat = meta.measured_latency
        print(f"Model: {m_id:30s} | Total Calls: {registry.get_telemetry(m_id).get('total_calls')} | Mean Latency: {lat.get('mean_ms')} ms | P95 Latency: {lat.get('p95_ms')} ms")

    print("\n" + "=" * 80)
    print("STAGE 4 DUAL-MODEL DEMONSTRATION COMPLETE: ALL INFERENCES UNIFIED")
    print("=" * 80)


if __name__ == "__main__":
    run_demonstration()
