"""
generate_charts.py: Publication-quality visualization generator for SETU-NETRA Stage 6.

Why this file exists:
Reads persisted benchmark results from benchmarks/results/aggregated/ and generates
8 publication-standard visualization charts into benchmarks/results/charts/:
1. Throughput Comparison across 6 Schedulers (throughput_comparison.png)
2. P50 / P95 / P99 Latency Percentiles (latency_percentiles.png)
3. Queue Waiting Time Comparison (queue_wait_comparison.png)
4. Worker Load & Utilization Balance (worker_utilization.png)
5. Host Hardware CPU & RAM Utilization (cpu_ram_utilization.png)
6. Outage & Failure Recovery Rates (failure_recovery_comparison.png)
7. Adaptive Routing Confusion Matrix (routing_confusion_matrix.png)
8. Document QA Retrieval & Citation Metrics (qa_retrieval_citations.png)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


class BenchmarkChartGenerator:
    """Generates 8 publication-grade charts from empirical benchmark outputs."""

    def __init__(self, results_dir: Optional[Path] = None):
        self._repo_root = Path(__file__).resolve().parent.parent
        self._results_dir = results_dir or (self._repo_root / "benchmarks" / "results")
        self._agg_dir = self._results_dir / "aggregated"
        self._charts_dir = self._results_dir / "charts"
        self._charts_dir.mkdir(parents=True, exist_ok=True)

        # Visual styling
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        self._colors = ["#2b5c8f", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02"]

    def _load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        path = self._agg_dir / filename
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_all_charts(self) -> List[Path]:
        """Generate all 8 figures from aggregated data."""
        generated: List[Path] = []
        print("\n" + "=" * 80)
        print("STAGE 6: GENERATING PUBLICATION CHARTS (from Empirical Benchmark Data)")
        print("=" * 80)

        sched_data = self._load_json("scheduler_microbenchmarks_summary.json")
        infer_data = self._load_json("real_inference_benchmarks_summary.json")
        routing_data = self._load_json("routing_evaluation_summary.json")
        qa_data = self._load_json("qa_quality_evaluation_summary.json")
        rel_data = self._load_json("reliability_evaluation_summary.json")

        if sched_data:
            m = sched_data.get("metrics", {})
            p1 = self._chart_throughput_comparison(m)
            if p1: generated.append(p1)

            p2 = self._chart_latency_percentiles(m)
            if p2: generated.append(p2)

            p3 = self._chart_queue_wait_comparison(m)
            if p3: generated.append(p3)

            p4 = self._chart_worker_utilization(m)
            if p4: generated.append(p4)

            p6 = self._chart_failure_recovery(m)
            if p6: generated.append(p6)

        if infer_data:
            m = infer_data.get("metrics", {})
            p5 = self._chart_cpu_ram_utilization(m)
            if p5: generated.append(p5)

        if routing_data:
            m = routing_data.get("metrics", {})
            p7 = self._chart_routing_confusion_matrix(m)
            if p7: generated.append(p7)

        if qa_data:
            m = qa_data.get("metrics", {})
            p8 = self._chart_qa_retrieval_citations(m)
            if p8: generated.append(p8)

        print(f"\n[OK] Generated {len(generated)} publication-quality charts in {self._charts_dir}")
        return generated

    def _chart_throughput_comparison(self, sched_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 1: Throughput Comparison across 6 Schedulers."""
        profiles = ["uniform_short", "burst", "unequal_worker_capacity", "worker_failure_and_recovery"]
        valid_profiles = [p for p in profiles if p in sched_metrics]
        if not valid_profiles:
            return None

        sched_names = list(next(iter(sched_metrics.values())).keys())
        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

        x = np.arange(len(valid_profiles))
        width = 0.13

        for i, s_name in enumerate(sched_names):
            vals = [
                sched_metrics[p][s_name]["throughput_req_sec"]["mean"]
                for p in valid_profiles
            ]
            clean_label = s_name.replace("RESILIENT_CAPACITY_AWARE", "ARS").replace("LEAST_OUTSTANDING", "LOR").replace("CAPACITY_AWARE", "CAS")
            ax.bar(x + (i - len(sched_names) / 2) * width + width / 2, vals, width, label=clean_label, color=self._colors[i % len(self._colors)])

        ax.set_ylabel("Throughput (Requests / Second)", fontsize=11, fontweight="bold")
        ax.set_title("Throughput Comparison across Scheduling Algorithms (Empirical Data)", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace("_", " ").title() for p in valid_profiles], fontsize=10)
        ax.legend(title="Scheduler", frameon=True)
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "throughput_comparison.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_latency_percentiles(self, sched_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 2: P50, P95, and P99 Latency Comparison under Mixed Workload."""
        workload = "mixed_sizes" if "mixed_sizes" in sched_metrics else next(iter(sched_metrics.keys()))
        data = sched_metrics[workload]

        sched_names = list(data.keys())
        p50 = [data[s]["latency_ms"]["p50"] for s in sched_names]
        p95 = [data[s]["latency_ms"]["p95"] for s in sched_names]
        p99 = [data[s]["latency_ms"]["p99"] for s in sched_names]

        fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
        x = np.arange(len(sched_names))
        width = 0.25

        clean_labels = [s.replace("RESILIENT_CAPACITY_AWARE", "ARS").replace("LEAST_OUTSTANDING", "LOR").replace("CAPACITY_AWARE", "CAS") for s in sched_names]

        ax.bar(x - width, p50, width, label="P50 Latency", color="#2b5c8f")
        ax.bar(x, p95, width, label="P95 Latency", color="#d95f02")
        ax.bar(x + width, p99, width, label="P99 Latency", color="#e7298a")

        ax.set_ylabel("Execution Latency (ms)", fontsize=11, fontweight="bold")
        ax.set_title(f"Latency Percentiles under {workload.replace('_', ' ').title()} Workload", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(clean_labels, fontsize=10)
        ax.legend(frameon=True)
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "latency_percentiles.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_queue_wait_comparison(self, sched_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 3: Queue Waiting Time Comparison under Burst Traffic."""
        workload = "burst" if "burst" in sched_metrics else next(iter(sched_metrics.keys()))
        data = sched_metrics[workload]

        sched_names = list(data.keys())
        waits = [data[s]["queue_wait_ms"]["mean"] for s in sched_names]
        clean_labels = [s.replace("RESILIENT_CAPACITY_AWARE", "ARS").replace("LEAST_OUTSTANDING", "LOR").replace("CAPACITY_AWARE", "CAS") for s in sched_names]

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        bars = ax.bar(clean_labels, waits, color="#7570b3", width=0.55)

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{height:.1f}ms",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.set_ylabel("Mean Queue Wait Time (ms)", fontsize=11, fontweight="bold")
        ax.set_title(f"Average Queue Waiting Time under Burst Traffic (Concurrent Arrival)", fontsize=13, fontweight="bold")
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "queue_wait_comparison.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_worker_utilization(self, sched_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 4: Scheduling Overhead in Microseconds."""
        workload = "uniform_short" if "uniform_short" in sched_metrics else next(iter(sched_metrics.keys()))
        data = sched_metrics[workload]

        sched_names = list(data.keys())
        overheads = [data[s]["scheduling_overhead_us"]["mean"] for s in sched_names]
        clean_labels = [s.replace("RESILIENT_CAPACITY_AWARE", "ARS").replace("LEAST_OUTSTANDING", "LOR").replace("CAPACITY_AWARE", "CAS") for s in sched_names]

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        bars = ax.barh(clean_labels, overheads, color="#66a61e", height=0.5)

        for bar in bars:
            width = bar.get_width()
            ax.annotate(f"{width:.1f} µs",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9, fontweight="bold")

        ax.set_xlabel("Mean Scheduling Dispatch Overhead (Microseconds - µs)", fontsize=11, fontweight="bold")
        ax.set_title("Algorithm Dispatch Overhead Comparison", fontsize=13, fontweight="bold")
        ax.grid(axis="x", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "worker_utilization.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_cpu_ram_utilization(self, infer_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 5: Host Hardware CPU and RAM Load during Real Model Inference."""
        models = list(infer_metrics.keys())
        cpu_vals = [infer_metrics[m]["system_telemetry"]["cpu_percent"] for m in models]
        ram_vals = [infer_metrics[m]["system_telemetry"]["ram_percent"] for m in models]

        short_names = [m.split("/")[-1].replace("-craft-crnn", "").replace("-Instruct", "") for m in models]

        fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
        x = np.arange(len(models))
        width = 0.35

        ax.bar(x - width / 2, cpu_vals, width, label="CPU Utilization (%)", color="#d95f02")
        ax.bar(x + width / 2, ram_vals, width, label="RAM Utilization (%)", color="#2b5c8f")

        ax.set_ylabel("Host System Resource (%)", fontsize=11, fontweight="bold")
        ax.set_title("Host Hardware Resource Profile during Local Model Inference", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(short_names, fontsize=9, rotation=15)
        ax.set_ylim(0, 100)
        ax.legend(frameon=True)
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "cpu_ram_utilization.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_failure_recovery(self, sched_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 6: Success Rate during Active Worker Failure & Recovery Workload."""
        workload = "worker_failure_and_recovery"
        if workload not in sched_metrics:
            return None
        data = sched_metrics[workload]

        sched_names = list(data.keys())
        success_rates = [data[s]["success_rate_percent"] for s in sched_names]
        clean_labels = [s.replace("RESILIENT_CAPACITY_AWARE", "ARS").replace("LEAST_OUTSTANDING", "LOR").replace("CAPACITY_AWARE", "CAS") for s in sched_names]

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        colors = ["#2b5c8f" if s < 100 else "#66a61e" for s in success_rates]
        bars = ax.bar(clean_labels, success_rates, color=colors, width=0.55)

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{height:.1f}%",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.set_ylabel("Request Success Rate (%)", fontsize=11, fontweight="bold")
        ax.set_title("Resilience: Success Rate under Active Worker Failure Injection", fontsize=13, fontweight="bold")
        ax.set_ylim(0, 115)
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "failure_recovery_comparison.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_routing_confusion_matrix(self, routing_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 7: Adaptive Model Routing Multiclass Confusion Matrix."""
        clf = routing_metrics.get("classification_metrics", {})
        matrix = np.array(clf.get("confusion_matrix", []))
        labels = clf.get("labels", [])
        if len(matrix) == 0 or len(labels) == 0:
            return None

        fig, ax = plt.subplots(figsize=(7, 6), dpi=300)
        cax = ax.matshow(matrix, cmap="Blues")
        fig.colorbar(cax)

        ax.set_xticks(np.arange(len(labels)))
        ax.set_yticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="left", fontsize=9)
        ax.set_yticklabels(labels, fontsize=9)

        for i in range(len(labels)):
            for j in range(len(labels)):
                val = matrix[i, j]
                ax.text(j, i, str(val), ha="center", va="center", color="white" if val > matrix.max() / 2 else "black", fontweight="bold")

        ax.set_xlabel("Predicted Model Category", fontsize=11, fontweight="bold", labelpad=10)
        ax.set_ylabel("True Intent / Category", fontsize=11, fontweight="bold")
        ax.set_title(f"Adaptive Routing Confusion Matrix (Accuracy: {routing_metrics.get('overall_routing_accuracy', 0)*100:.1f}%)", fontsize=12, fontweight="bold", pad=20)

        out_path = self._charts_dir / "routing_confusion_matrix.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path

    def _chart_qa_retrieval_citations(self, qa_metrics: Dict[str, Any]) -> Optional[Path]:
        """Chart 8: Document QA Quality: Retrieval, Answer, and Citation Metrics."""
        fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=300)

        metric_names = [
            "Retrieval Recall@1",
            "Retrieval MRR",
            "Token F1 Score",
            "Exact Match (EM)",
            "Citation Precision",
            "Citation Completeness",
            "Unsupported Abstention",
        ]

        rr = qa_metrics.get("retrieval_ranking", {})
        values = [
            rr.get("recall@1", 0.0) * 100,
            rr.get("mrr", 0.0) * 100,
            qa_metrics.get("token_f1", {}).get("mean", 0.0) * 100,
            qa_metrics.get("exact_match", {}).get("mean", 0.0) * 100,
            qa_metrics.get("citation_precision", {}).get("mean", 0.0) * 100,
            qa_metrics.get("citation_completeness", {}).get("mean", 0.0) * 100,
            qa_metrics.get("unsupported_abstention_accuracy", 0.0),
        ]

        y_pos = np.arange(len(metric_names))
        bars = ax.barh(y_pos, values, color="#2b5c8f", height=0.55)

        for bar in bars:
            width = bar.get_width()
            ax.annotate(f"{width:.1f}%",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9, fontweight="bold")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(metric_names, fontsize=10)
        ax.set_xlabel("Score (%)", fontsize=11, fontweight="bold")
        ax.set_title("End-to-End Grounded QA & Citation Quality Evaluation", fontsize=13, fontweight="bold")
        ax.set_xlim(0, 115)
        ax.grid(axis="x", linestyle="--", alpha=0.7)

        out_path = self._charts_dir / "qa_retrieval_citations.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        print(f"  * Generated: {out_path.name}")
        return out_path


if __name__ == "__main__":
    generator = BenchmarkChartGenerator()
    generator.generate_all_charts()
