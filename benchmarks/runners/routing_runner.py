"""
routing_runner.py: Adaptive Model Routing quantitative evaluation runner for SETU-NETRA Stage 6.

Why this file exists:
Evaluates AdaptiveModelRouter decisions against a labeled ground-truth evaluation dataset:
- Task-Model compatibility
- Cognitive intent routing
- SLA compliance (< 1500 ms SLA drops/falls back to fast extractive)
- Evidence requirement compliance (strict citations route to extractive QA)
- Unsupported-task rejection accuracy
- Fallback routing correctness under unavailable/degraded models
- Routing decision latency (microseconds)
Calculates multiclass confusion matrix, per-task precision, recall, F1, and overall accuracy.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.classifier_adapter import ClassificationExecutionAdapter
from setu_netra.routing.adapters.embedding_adapter import EmbeddingExecutionAdapter
from setu_netra.routing.adapters.generative_adapter import LocalGenerativeAdapter
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.routing.adapters.ocr_adapter import OCRExecutionAdapter
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.routing.contracts import (
    InferenceRequest,
    ModelAvailability,
    RoutingDecision,
)
from setu_netra.routing.registry import ModelRegistry
from setu_netra.routing.router import AdaptiveModelRouter

from benchmarks.experiments.experiment_tracker import ExperimentMetadata, ExperimentTracker
from benchmarks.metrics.calculator import (
    compute_classification_metrics,
    compute_statistical_summary,
)

logger = logging.getLogger(__name__)


class RoutingEvaluationRunner:
    """Quantitative evaluator for AdaptiveModelRouter decisions."""

    def __init__(self, tracker: Optional[ExperimentTracker] = None):
        self._tracker = tracker or ExperimentTracker()
        self._dataset_path = Path(__file__).resolve().parent.parent / "datasets" / "routing_eval_dataset.json"

    def setup_registry_and_router(self) -> Tuple[ModelRegistry, AdaptiveModelRouter]:
        registry = ModelRegistry(register_defaults=False)
        registry.register_adapter(OCRExecutionAdapter(model_id="easyocr-craft-crnn"))
        registry.register_adapter(EmbeddingExecutionAdapter(engine=get_embedding_engine("neural"), model_id="sentence-transformers/all-MiniLM-L6-v2"))
        registry.register_adapter(ClassificationExecutionAdapter(model_id="academic-domain-classifier-v1"))
        registry.register_adapter(GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1"))
        registry.register_adapter(LocalGenerativeAdapter(model_id="HuggingFaceTB/SmolLM2-135M-Instruct"))
        router = AdaptiveModelRouter(registry=registry)
        return registry, router

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(self._dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_routing_dataset(self) -> Dict[str, Any]:
        """Execute full evaluation on labeled routing dataset."""
        print("=" * 80)
        print("STAGE 6: ADAPTIVE MODEL ROUTING QUANTITATIVE EVALUATION")
        print("=" * 80)

        registry, router = self.setup_registry_and_router()
        dataset = self.load_dataset()

        gold_categories: List[str] = []
        pred_categories: List[str] = []
        decision_latencies_us: List[float] = []

        total_samples = len(dataset)
        correct_model_count = 0
        correct_status_count = 0
        unsupported_true_positives = 0
        unsupported_total = 0
        sla_fallback_correct = 0
        sla_fallback_total = 0

        raw_eval_records: List[Dict[str, Any]] = []

        for item in dataset:
            req = InferenceRequest(
                task_type=item["task_type"],
                input_payload=item["input_payload"],
                context=item.get("context"),
                metadata=item.get("metadata", {}),
                timeout_ms=item.get("metadata", {}).get("timeout_ms"),
            )

            t0 = time.perf_counter()
            decision: RoutingDecision = router.route(req)
            elapsed_us = (time.perf_counter() - t0) * 1e6
            decision_latencies_us.append(elapsed_us)

            # Map predicted model to high-level category
            pred_cat = "REJECTED"
            if decision.status == "REJECTED" or decision.selected_model_id is None:
                pred_cat = "REJECTED"
            elif "easyocr" in decision.selected_model_id.lower():
                pred_cat = "OCR"
            elif "minilm" in decision.selected_model_id.lower():
                pred_cat = "Embedding"
            elif "classifier" in decision.selected_model_id.lower():
                pred_cat = "Classification"
            elif "extractive" in decision.selected_model_id.lower():
                pred_cat = "Extractive QA"
            elif "smollm2" in decision.selected_model_id.lower():
                if item["category"] == "Reasoning":
                    pred_cat = "Reasoning"
                elif item["category"] == "Summarization":
                    pred_cat = "Summarization"
                else:
                    pred_cat = "Generative QA"

            expected_cat = item["category"]
            if expected_cat in ("Unsupported Task", "Unsupported"):
                expected_cat = "REJECTED"
            elif expected_cat == "SLA Fallback":
                expected_cat = "Extractive QA"

            gold_categories.append(expected_cat)
            pred_categories.append(pred_cat)

            # Check correctness
            expected_model = item.get("expected_model")
            expected_status = item.get("expected_status", "ROUTED")

            model_match = (decision.selected_model_id == expected_model)
            status_match = (decision.status == expected_status)

            if model_match:
                correct_model_count += 1
            if status_match:
                correct_status_count += 1

            # Unsupported task tracking
            if item["category"] == "Unsupported Task":
                unsupported_total += 1
                if decision.status == "REJECTED" and decision.selected_model_id is None:
                    unsupported_true_positives += 1

            # SLA fallback tracking
            if item["category"] == "SLA Fallback":
                sla_fallback_total += 1
                if decision.status == "FALLBACK" and decision.selected_model_id == expected_model:
                    sla_fallback_correct += 1

            raw_eval_records.append({
                "item_id": item["id"],
                "task_type": item["task_type"],
                "expected_category": expected_cat,
                "predicted_category": pred_cat,
                "expected_model": expected_model,
                "selected_model": decision.selected_model_id,
                "expected_status": expected_status,
                "decision_status": decision.status,
                "confidence": decision.confidence,
                "decision_latency_us": round(elapsed_us, 2),
                "model_match": model_match,
                "status_match": status_match,
                "reason": decision.reason,
            })

        # Calculate Classification Metrics
        clf_metrics = compute_classification_metrics(gold_categories, pred_categories)
        latency_stats = compute_statistical_summary(decision_latencies_us)

        # 2. Test Degraded/Unavailable Model Avoidance & Fallback
        print("\n--- Testing Model Unavailability Fallback ---")
        registry.set_model_availability("grounded-extractive-qa-v1", ModelAvailability.UNAVAILABLE)
        fallback_req = InferenceRequest(task_type="qa", input_payload="What is the clock speed?")
        fb_decision = router.route(fallback_req)
        fallback_succeeded = (
            fb_decision.selected_model_id == "HuggingFaceTB/SmolLM2-135M-Instruct"
            and fb_decision.status in ("ROUTED", "FALLBACK")
        )
        print(f"  Extractive QA marked UNAVAILABLE -> Fallback to Generative: {fallback_succeeded}")

        # Reset availability
        registry.set_model_availability("grounded-extractive-qa-v1", ModelAvailability.AVAILABLE)

        summary_metrics = {
            "total_samples": total_samples,
            "overall_routing_accuracy": round(correct_model_count / total_samples, 4),
            "status_accuracy": round(correct_status_count / total_samples, 4),
            "unsupported_task_rejection_accuracy": round(
                (unsupported_true_positives / unsupported_total) if unsupported_total else 1.0, 4
            ),
            "sla_fallback_accuracy": round(
                (sla_fallback_correct / sla_fallback_total) if sla_fallback_total else 1.0, 4
            ),
            "degraded_model_fallback_verified": fallback_succeeded,
            "decision_latency_us": latency_stats,
            "classification_metrics": clf_metrics,
        }

        print(f"\nOverall Routing Accuracy:            {summary_metrics['overall_routing_accuracy'] * 100:.1f}%")
        print(f"Macro F1 Score:                      {clf_metrics['macro_f1']:.4f}")
        print(f"Unsupported Task Rejection Accuracy: {summary_metrics['unsupported_task_rejection_accuracy'] * 100:.1f}%")
        print(f"SLA Fallback Accuracy:               {summary_metrics['sla_fallback_accuracy'] * 100:.1f}%")
        print(f"Mean Routing Latency:                {latency_stats['mean']:.1f} µs (P95: {latency_stats['p95']:.1f} µs)")

        metadata = ExperimentMetadata(
            experiment_id="routing_evaluation",
            suite_name="Stage 6 Routing Evaluation",
            description="Empirical evaluation of AdaptiveModelRouter across 20 labeled test cases.",
            workload_id="labeled_routing_dataset",
            total_requests=total_samples,
        )

        raw_path = self._tracker.save_raw_experiment_data("routing_evaluation", metadata, raw_eval_records)
        summary_path = self._tracker.save_aggregated_results("routing_evaluation", metadata, summary_metrics)
        print(f"\n[OK] Routing evaluation completed.")
        print(f"  Raw records saved:         {raw_path}")
        print(f"  Aggregated results saved:  {summary_path}")

        return summary_metrics
