"""
run_full_evaluation.py: Master end-to-end evaluation orchestrator for SETU-NETRA Stage 6.

Why this file exists:
Provides a single unified CLI command to execute all Stage 6 experimental validation suites:
1. Scheduler Microbenchmarks (6 Schedulers x 8 Workloads)
2. Real AI Model Inference Benchmarks (EasyOCR, MiniLM, Offline, Extractive QA, SmolLM2-135M)
3. Adaptive Model Routing Evaluation (Accuracy, Confusion Matrix, SLA, Fallback)
4. Document QA Quality & Citation Verification (MRR, Token F1, Exact Match, Citation Precision)
5. Reliability & Fault Recovery Tests (Circuit Breaking, Timeouts, Failover, Backpressure)
6. Publication Chart Generation (8 PNG Figures)

Usage:
    python benchmarks/run_full_evaluation.py [--fast]
"""

import argparse
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.experiments.experiment_tracker import ExperimentTracker
from benchmarks.generate_charts import BenchmarkChartGenerator
from benchmarks.runners.inference_runner import RealInferenceBenchmarkRunner
from benchmarks.runners.qa_runner import DocumentQAEvaluationRunner
from benchmarks.runners.reliability_runner import ReliabilityBenchmarkRunner
from benchmarks.runners.routing_runner import RoutingEvaluationRunner
from benchmarks.runners.scheduler_runner import SchedulerBenchmarkRunner


def run_full_suite(fast_mode: bool = False):
    total_start = time.perf_counter()
    tracker = ExperimentTracker()

    print("#" * 80)
    print("SETU-NETRA STAGE 6: FULL EXPERIMENTAL VALIDATION & BENCHMARK SUITE")
    print("Mode: " + ("FAST (2 Reps x 15 Reqs)" if fast_mode else "STANDARD (3 Reps x 25 Reqs)"))
    print("#" * 80)

    # 1. Scheduler Microbenchmarks
    reps = 2 if fast_mode else 3
    reqs_per_rep = 15 if fast_mode else 25
    sched_runner = SchedulerBenchmarkRunner(tracker=tracker)
    sched_results = sched_runner.execute_full_suite(
        repetition_count=reps,
        requests_per_rep=reqs_per_rep,
    )

    # 2. Real AI Model Inference Benchmarks
    infer_runner = RealInferenceBenchmarkRunner(tracker=tracker)
    infer_results = infer_runner.execute_all_inference_benchmarks()

    # 3. Adaptive Model Routing Evaluation
    routing_runner = RoutingEvaluationRunner(tracker=tracker)
    routing_results = routing_runner.evaluate_routing_dataset()

    # 4. Document QA Quality Evaluation
    qa_runner = DocumentQAEvaluationRunner(tracker=tracker)
    qa_results = qa_runner.execute_qa_evaluation()

    # 5. Reliability & Fault Recovery Tests
    rel_runner = ReliabilityBenchmarkRunner(tracker=tracker)
    rel_results = rel_runner.execute_all_reliability_tests()

    # 6. Generate Publication Charts
    chart_gen = BenchmarkChartGenerator()
    generated_charts = chart_gen.generate_all_charts()

    total_time_sec = time.perf_counter() - total_start

    print("\n" + "#" * 80)
    print("STAGE 6 FULL EVALUATION COMPLETED SUCCESSFULLY")
    print(f"Total Execution Time: {total_time_sec:.1f} seconds ({total_time_sec / 60.0:.2f} minutes)")
    print(f"Generated Publication Figures: {len(generated_charts)}")
    for c in generated_charts:
        print(f"  - {c.name}")
    print("#" * 80)


def main():
    parser = argparse.ArgumentParser(description="Execute SETU-NETRA Stage 6 Full Evaluation Suite")
    parser.add_argument("--fast", action="store_true", help="Run with reduced repetition count for fast validation")
    args = parser.parse_args()
    run_full_suite(fast_mode=args.fast)


if __name__ == "__main__":
    main()
