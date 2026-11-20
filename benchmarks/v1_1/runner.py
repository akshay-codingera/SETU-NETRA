"""
runner.py: Master experimental orchestrator for SETU-NETRA V1.1 baseline experiments.
Coordinates:
- Corpus ingestion into isolated database (output/v1_1_benchmark_store.db)
- 2x2 Factorial QA Quality benchmark (N=100 queries x 4 conditions)
- 2x2 Factorial Synthetic Scheduler Load benchmark (N=1,000 requests x 4 conditions)
- Concurrent End-to-End Document QA Load benchmark
- Full statistical analysis (RM-ANOVA, McNemar, Wilcoxon, Bootstrap CIs)
- Persistence of raw per-request records and aggregated baseline summary
"""

import argparse
import concurrent.futures
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Adjust python path if necessary
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "src"))
sys.path.insert(0, str(root_dir))

from benchmarks.v1_1.harness.corpus_loader import setup_benchmark_corpus
from benchmarks.v1_1.harness.load_generator import run_scheduler_load_benchmark
from benchmarks.v1_1.harness.metrics import (
    bootstrap_confidence_interval,
    compute_percentiles_with_ci,
)
from benchmarks.v1_1.harness.query_runner import (
    BenchmarkQAEngine,
    run_qa_quality_benchmark,
)
from benchmarks.v1_1.harness.statistical_analyzer import (
    compute_mcnemar_test,
    compute_paired_wilcoxon,
    compute_repeated_measures_factorial_anova,
)
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import get_model_registry
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.schedulers.round_robin import RoundRobinScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("v1_1_runner")


def ensure_dirs():
    """Ensure data output directory exists."""
    data_dir = Path("benchmarks/v1_1/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)


def load_condition_configs() -> Dict[str, Dict[str, Any]]:
    """Loads the four condition configuration files."""
    configs = {}
    config_dir = Path("benchmarks/v1_1/configs")
    for cfile in sorted(config_dir.glob("condition_*.json")):
        with open(cfile, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            configs[cfg["condition_id"]] = cfg
    return configs


def execute_quality_suite(
    doc_pipeline: DocumentIntelligencePipeline,
    configs: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs the 100-query QA quality evaluation across all 4 conditions."""
    logger.info("=== Starting QA Quality Suite (100 queries x 4 conditions) ===")
    raw_by_condition = {}
    summaries = {}

    for cond_id, cfg in configs.items():
        logger.info("Executing Quality Benchmark for %s (%s)...", cond_id, cfg["name"])
        raw, summary = run_qa_quality_benchmark(
            condition_name=cond_id,
            doc_pipeline=doc_pipeline,
            queries_path="benchmarks/v1_1/queries/qa_evaluation_queries.json",
            scheduler_type=cfg["scheduler"],
            fixed_model_id=cfg["fixed_model_id"],
        )
        raw_by_condition[cond_id] = raw
        summaries[cond_id] = summary

        # Save individual raw records
        out_raw_file = Path(f"benchmarks/v1_1/data/raw_quality_{cond_id}.json")
        with open(out_raw_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
        logger.info("Saved raw records to %s", out_raw_file)

    # Formal Statistical Analysis
    logger.info("Computing 2x2 Repeated-Measures Factorial ANOVA and pairwise tests...")
    anova_em = compute_repeated_measures_factorial_anova(
        y00=[r["exact_match"] for r in raw_by_condition["Condition_A"]],
        y01=[r["exact_match"] for r in raw_by_condition["Condition_B"]],
        y10=[r["exact_match"] for r in raw_by_condition["Condition_C"]],
        y11=[r["exact_match"] for r in raw_by_condition["Condition_D"]],
        metric_name="Exact_Match",
    )
    anova_f1 = compute_repeated_measures_factorial_anova(
        y00=[r["token_f1"] for r in raw_by_condition["Condition_A"]],
        y01=[r["token_f1"] for r in raw_by_condition["Condition_B"]],
        y10=[r["token_f1"] for r in raw_by_condition["Condition_C"]],
        y11=[r["token_f1"] for r in raw_by_condition["Condition_D"]],
        metric_name="Token_F1",
    )
    anova_citation = compute_repeated_measures_factorial_anova(
        y00=[r["citation_precision"] for r in raw_by_condition["Condition_A"]],
        y01=[r["citation_precision"] for r in raw_by_condition["Condition_B"]],
        y10=[r["citation_precision"] for r in raw_by_condition["Condition_C"]],
        y11=[r["citation_precision"] for r in raw_by_condition["Condition_D"]],
        metric_name="Citation_Precision",
    )
    anova_latency = compute_repeated_measures_factorial_anova(
        y00=[r["total_latency_ms"] for r in raw_by_condition["Condition_A"]],
        y01=[r["total_latency_ms"] for r in raw_by_condition["Condition_B"]],
        y10=[r["total_latency_ms"] for r in raw_by_condition["Condition_C"]],
        y11=[r["total_latency_ms"] for r in raw_by_condition["Condition_D"]],
        metric_name="Total_Latency_ms",
    )

    # McNemar's tests between conditions on Exact Match
    mcnemar_a_vs_c = compute_mcnemar_test(
        condition1_binary=[int(r["exact_match"]) for r in raw_by_condition["Condition_A"]],
        condition2_binary=[int(r["exact_match"]) for r in raw_by_condition["Condition_C"]],
    )
    mcnemar_a_vs_d = compute_mcnemar_test(
        condition1_binary=[int(r["exact_match"]) for r in raw_by_condition["Condition_A"]],
        condition2_binary=[int(r["exact_match"]) for r in raw_by_condition["Condition_D"]],
    )

    # Wilcoxon signed-rank tests for F1 and Latency
    wilcoxon_f1_a_vs_c = compute_paired_wilcoxon(
        condition1_scores=[r["token_f1"] for r in raw_by_condition["Condition_A"]],
        condition2_scores=[r["token_f1"] for r in raw_by_condition["Condition_C"]],
        metric_name="Token_F1",
    )
    wilcoxon_lat_a_vs_d = compute_paired_wilcoxon(
        condition1_scores=[r["total_latency_ms"] for r in raw_by_condition["Condition_A"]],
        condition2_scores=[r["total_latency_ms"] for r in raw_by_condition["Condition_D"]],
        metric_name="Total_Latency_ms",
    )

    statistical_report = {
        "anova_exact_match": anova_em,
        "anova_token_f1": anova_f1,
        "anova_citation_precision": anova_citation,
        "anova_total_latency": anova_latency,
        "mcnemar_exact_match": {
            "a_vs_c": mcnemar_a_vs_c,
            "a_vs_d": mcnemar_a_vs_d,
        },
        "wilcoxon_token_f1": {
            "a_vs_c": wilcoxon_f1_a_vs_c,
        },
        "wilcoxon_latency": {
            "a_vs_d": wilcoxon_lat_a_vs_d,
        },
    }

    quality_results = {
        "summaries": summaries,
        "statistical_tests": statistical_report,
    }
    return raw_by_condition, quality_results


def execute_load_suite(
    configs: Dict[str, Dict[str, Any]],
    total_requests: int = 1000,
    arrival_rate_lambda: float = 25.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs the synthetic scheduler load benchmark (N >= 1,000 requests) across all 4 conditions."""
    logger.info(
        "=== Starting Synthetic Scheduler Load Suite (%d requests per condition, lambda=%.1f) ===",
        total_requests,
        arrival_rate_lambda,
    )
    raw_by_condition = {}
    summaries = {}

    for cond_id, cfg in configs.items():
        logger.info("Executing Load Benchmark for %s (%s)...", cond_id, cfg["name"])
        scheduler = (
            CapacityAwareScheduler() if cfg["scheduler"] == "CAPACITY_AWARE" else RoundRobinScheduler()
        )
        is_adaptive = cfg["routing_policy"] == "adaptive"

        raw, summary = run_scheduler_load_benchmark(
            condition_name=cond_id,
            scheduler=scheduler,
            total_requests=total_requests,
            arrival_rate_lambda=arrival_rate_lambda,
            num_client_threads=8,
            is_adaptive_routing=is_adaptive,
            random_seed=42,
        )
        raw_by_condition[cond_id] = raw
        summaries[cond_id] = summary

        out_raw_file = Path(f"benchmarks/v1_1/data/raw_load_{cond_id}.json")
        with open(out_raw_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
        logger.info("Saved raw load records to %s", out_raw_file)

    # Compute Factorial ANOVA on Latency and Queue Wait Time under load
    anova_load_lat = compute_repeated_measures_factorial_anova(
        y00=[r["total_latency_ms"] for r in raw_by_condition["Condition_A"] if r["status"] == "SUCCESS"][:900],
        y01=[r["total_latency_ms"] for r in raw_by_condition["Condition_B"] if r["status"] == "SUCCESS"][:900],
        y10=[r["total_latency_ms"] for r in raw_by_condition["Condition_C"] if r["status"] == "SUCCESS"][:900],
        y11=[r["total_latency_ms"] for r in raw_by_condition["Condition_D"] if r["status"] == "SUCCESS"][:900],
        metric_name="Synthetic_Load_Latency_ms",
    )
    anova_load_wait = compute_repeated_measures_factorial_anova(
        y00=[r["queue_wait_ms"] for r in raw_by_condition["Condition_A"] if r["status"] == "SUCCESS"][:900],
        y01=[r["queue_wait_ms"] for r in raw_by_condition["Condition_B"] if r["status"] == "SUCCESS"][:900],
        y10=[r["queue_wait_ms"] for r in raw_by_condition["Condition_C"] if r["status"] == "SUCCESS"][:900],
        y11=[r["queue_wait_ms"] for r in raw_by_condition["Condition_D"] if r["status"] == "SUCCESS"][:900],
        metric_name="Synthetic_Queue_Wait_ms",
    )

    load_results = {
        "summaries": summaries,
        "statistical_tests": {
            "anova_load_latency": anova_load_lat,
            "anova_load_queue_wait": anova_load_wait,
        },
    }
    return raw_by_condition, load_results


def execute_e2e_qa_load_suite(
    doc_pipeline: DocumentIntelligencePipeline,
    configs: Dict[str, Dict[str, Any]],
    num_requests: int = 20,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs multi-threaded concurrent End-to-End Document QA load test against live pipeline."""
    logger.info("=== Starting End-to-End Document QA Concurrent Load Suite (%d requests) ===", num_requests)
    with open("benchmarks/v1_1/queries/qa_evaluation_queries.json", "r", encoding="utf-8") as f:
        all_queries = json.load(f)

    # Filter to supported queries for load evaluation
    supported_queries = [q for q in all_queries if q.get("is_supported", True)]
    selected_queries = [supported_queries[i % len(supported_queries)] for i in range(num_requests)]

    raw_by_condition = {}
    summaries = {}

    for cond_id, cfg in configs.items():
        logger.info("Executing E2E QA Load Benchmark for %s (%s)...", cond_id, cfg["name"])
        registry = get_model_registry()
        scheduler = (
            CapacityAwareScheduler() if cfg["scheduler"] == "CAPACITY_AWARE" else RoundRobinScheduler()
        )
        inf_pipeline = IntelligentInferencePipeline(
            registry=registry,
            scheduler=scheduler,
            auto_spawn_workers=True,
        )
        qa_engine = BenchmarkQAEngine(
            retriever=doc_pipeline.retriever,
            inference_pipeline=inf_pipeline,
            fixed_model_id=cfg["fixed_model_id"],
        )

        records = []
        start_time = time.perf_counter()

        def run_one(idx: int, qitem: Dict[str, Any]) -> Dict[str, Any]:
            qid = f"E2E_{cond_id}_{idx:04d}"
            try:
                ans, trace = qa_engine.answer_question_benchmark(
                    query=qitem["question"],
                    query_id=qid,
                    condition_name=cond_id,
                )
                return {
                    "request_id": qid,
                    "query_index": idx,
                    "condition": cond_id,
                    "selected_model": trace["selected_model"],
                    "selected_worker": trace["selected_worker"],
                    "queue_wait_ms": trace["queue_wait_ms"],
                    "retrieval_time_ms": trace["retrieval_time_ms"],
                    "execution_time_ms": trace["execution_time_ms"],
                    "total_latency_ms": trace["total_latency_ms"],
                    "status": trace["status"],
                    "epistemic_status": trace["epistemic_status"],
                }
            except Exception as err:
                return {
                    "request_id": qid,
                    "query_index": idx,
                    "condition": cond_id,
                    "selected_model": cfg.get("fixed_model_id") or "auto",
                    "selected_worker": "none",
                    "queue_wait_ms": 0.0,
                    "retrieval_time_ms": 0.0,
                    "execution_time_ms": 0.0,
                    "total_latency_ms": 30000.0,
                    "status": "REJECTED",
                    "epistemic_status": "CIRCUIT_BREAKER_TRIPPED",
                    "error": str(err),
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_one, i, selected_queries[i]) for i in range(num_requests)]
            for fut in concurrent.futures.as_completed(futures):
                records.append(fut.result())

        duration = time.perf_counter() - start_time
        inf_pipeline.shutdown()

        records.sort(key=lambda r: r["query_index"])
        raw_by_condition[cond_id] = records

        # Save raw E2E records
        out_raw_file = Path(f"benchmarks/v1_1/data/raw_e2e_{cond_id}.json")
        with open(out_raw_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        latencies = [r["total_latency_ms"] for r in records if r["status"] == "SUCCESS"]
        pct_lat = compute_percentiles_with_ci(latencies, percentiles=(50.0, 95.0, 99.0))
        success_cnt = sum(1 for r in records if r["status"] == "SUCCESS")

        summaries[cond_id] = {
            "condition": cond_id,
            "total_requests": num_requests,
            "total_duration_sec": round(duration, 2),
            "success_count": success_cnt,
            "rejection_count": num_requests - success_cnt,
            "rejection_rate": round((num_requests - success_cnt) / num_requests, 4),
            "throughput_req_per_sec": round(num_requests / duration, 2) if duration > 0 else 0.0,
            "latency_percentiles_ms": pct_lat,
            "mean_total_latency_ms": round(float(np.mean(latencies)), 2) if latencies else 0.0,
            "mean_retrieval_time_ms": round(float(np.mean([r["retrieval_time_ms"] for r in records if r["status"] == "SUCCESS"])), 2) if latencies else 0.0,
            "mean_execution_time_ms": round(float(np.mean([r["execution_time_ms"] for r in records if r["status"] == "SUCCESS"])), 2) if latencies else 0.0,
        }

    return raw_by_condition, {"summaries": summaries}


def main():
    parser = argparse.ArgumentParser(description="SETU-NETRA V1.1 Baseline Experimental Runner")
    parser.add_argument(
        "--mode",
        choices=["corpus", "quality", "load", "e2e", "all"],
        default="all",
        help="Benchmark execution mode",
    )
    parser.add_argument(
        "--db-path",
        default="output/v1_1_benchmark_store.db",
        help="Path to benchmark SQLite database",
    )
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Reindex documents from scratch even if db exists",
    )
    parser.add_argument(
        "--load-requests",
        type=int,
        default=1000,
        help="Number of requests per condition for synthetic load test",
    )
    args = parser.parse_args()

    ensure_dirs()
    configs = load_condition_configs()
    logger.info("Loaded configs for conditions: %s", list(configs.keys()))

    master_file = Path("benchmarks/v1_1/data/aggregated_baseline_results.json")
    if master_file.exists():
        try:
            with open(master_file, "r", encoding="utf-8") as f:
                aggregated_results = json.load(f)
        except Exception:
            aggregated_results = {}
    else:
        aggregated_results = {}

    aggregated_results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    aggregated_results["manifest_path"] = "benchmarks/v1_1/manifest.json"
    aggregated_results["conditions"] = configs

    doc_pipeline = None

    if args.mode in ("corpus", "quality", "e2e", "all"):
        logger.info("Setting up benchmark corpus in %s...", args.db_path)
        doc_pipeline, doc_mapping = setup_benchmark_corpus(
            db_path=args.db_path,
            corpus_dir="benchmarks/v1_1/corpus",
            force_reindex=args.force_reindex,
        )
        aggregated_results["corpus_doc_mapping"] = doc_mapping
        logger.info("Corpus setup complete. Ingested docs: %s", doc_mapping)

    if args.mode in ("quality", "all"):
        raw_qual, quality_res = execute_quality_suite(doc_pipeline, configs)
        aggregated_results["qa_quality_benchmark"] = quality_res

    if args.mode in ("load", "all"):
        raw_load, load_res = execute_load_suite(
            configs,
            total_requests=args.load_requests,
            arrival_rate_lambda=25.0,
        )
        aggregated_results["synthetic_load_benchmark"] = load_res

    if args.mode in ("e2e", "all"):
        raw_e2e, e2e_res = execute_e2e_qa_load_suite(
            doc_pipeline,
            configs,
            num_requests=20,
        )
        aggregated_results["e2e_qa_load_benchmark"] = e2e_res

    # Dump master aggregated JSON
    master_file = Path("benchmarks/v1_1/data/aggregated_baseline_results.json")
    with open(master_file, "w", encoding="utf-8") as f:
        json.dump(aggregated_results, f, indent=2)
    logger.info("=== MASTER AGGREGATED BASELINE DUMPED TO %s ===", master_file)


if __name__ == "__main__":
    main()
