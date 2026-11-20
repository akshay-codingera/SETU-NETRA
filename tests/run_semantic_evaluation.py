"""
run_semantic_evaluation.py: Formal empirical evaluation and backend comparison for Module 4.

Why this file exists:
Computes objective, reproducible quantitative metrics (Accuracy, Precision, Recall, Macro-F1,
Intent Accuracy, Abstention Accuracy, and Latency) for both:
1. The deterministic offline feature-hashing baseline ('offline_semantic_tfidf')
2. The real pretrained SentenceTransformer backend ('all-MiniLM-L6-v2')
across held-out benchmark cases, measuring actual CPU performance without hallucinating results.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.semantic.engine import SemanticUnderstandingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine


def evaluate_single_backend(
    engine_name: str,
    benchmark_data: List[Dict[str, Any]],
    output_dir: Path,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run full quantitative evaluation suite for a single embedding backend."""
    embed_engine = get_embedding_engine(engine_name)
    engine = SemanticUnderstandingEngine(embedding_engine=embed_engine)

    if verbose:
        print("\n" + "=" * 80)
        print(f"  EVALUATING BACKEND: {engine.embedding_engine_name} (dim={embed_engine.dimension})")
        print("=" * 80)

    latencies: List[float] = []
    domain_true: List[str] = []
    domain_pred: List[str] = []

    intent_matches = 0
    total_intent_tests = 0

    abstention_true_positives = 0
    total_abstention_cases = 0

    results_log = []

    for item in benchmark_data:
        item_id = item["id"]
        text = item["text"]
        expected_domain = item["expected_domain"]
        expected_intents: Set[str] = set(item.get("expected_intents", []))
        is_abstention: bool = item.get("is_abstention", False)

        t0 = time.perf_counter()
        analysis = engine.analyze_text(text, source_id=item_id)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        pred_domain = analysis.primary_domain or "UNKNOWN_DOMAIN"
        pred_intents = set(analysis.question_intents)

        # 1. Domain Tracking
        if is_abstention:
            total_abstention_cases += 1
            if analysis.status in ("UNKNOWN_DOMAIN", "INSUFFICIENT_EVIDENCE") or pred_domain == "UNKNOWN_DOMAIN":
                abstention_true_positives += 1
        else:
            domain_true.append(expected_domain)
            domain_pred.append(pred_domain)

        # 2. Intent Tracking (Partial overlap counted as success for multi-intent)
        if expected_intents:
            total_intent_tests += 1
            if expected_intents.intersection(pred_intents):
                intent_matches += 1

        results_log.append({
            "id": item_id,
            "category": item.get("category"),
            "text": text,
            "expected_domain": expected_domain,
            "predicted_domain": pred_domain,
            "expected_intents": list(expected_intents),
            "predicted_intents": list(pred_intents),
            "status": analysis.status,
            "latency_ms": round(elapsed_ms, 2),
            "concepts": [c.normalized_form for c in analysis.concepts],
        })

    # Compute Domain Classification Metrics (Precision, Recall, F1 per class and macro)
    classes = sorted(list(set(domain_true + domain_pred)))
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for yt, yp in zip(domain_true, domain_pred):
        if yt == yp:
            tp[yt] += 1
        else:
            fp[yp] += 1
            fn[yt] += 1

    precisions = {}
    recalls = {}
    f1s = {}

    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        precisions[c] = p
        recalls[c] = r
        f1s[c] = f1

    macro_p = sum(precisions.values()) / max(1, len(precisions))
    macro_r = sum(recalls.values()) / max(1, len(recalls))
    macro_f1 = sum(f1s.values()) / max(1, len(f1s))
    domain_accuracy = sum(tp.values()) / max(1, len(domain_true))

    intent_acc = intent_matches / max(1, total_intent_tests)
    abstention_acc = abstention_true_positives / max(1, total_abstention_cases) if total_abstention_cases > 0 else 1.0
    mean_lat = sum(latencies) / len(latencies)

    summary_metrics = {
        "engine_name": engine.embedding_engine_name,
        "dimension": embed_engine.dimension,
        "total_cases": len(benchmark_data),
        "domain_accuracy": round(domain_accuracy, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "intent_accuracy": round(intent_acc, 4),
        "abstention_accuracy": round(abstention_acc, 4),
        "mean_latency_ms": round(mean_lat, 2),
        "per_class_f1": {k: round(v, 4) for k, v in f1s.items()},
        "detailed_results": results_log,
    }

    if verbose:
        print(f"  Domain Classification Accuracy:        {domain_accuracy * 100:.2f}% ({sum(tp.values())}/{len(domain_true)})")
        print(f"  Macro-Averaged Precision:              {macro_p * 100:.2f}%")
        print(f"  Macro-Averaged Recall:                 {macro_r * 100:.2f}%")
        print(f"  Macro-Averaged F1-Score:               {macro_f1 * 100:.2f}%")
        print(f"  Question Intent Match Accuracy:        {intent_acc * 100:.2f}% ({intent_matches}/{total_intent_tests})")
        print(f"  Abstention / Open-Set Accuracy:        {abstention_acc * 100:.2f}% ({abstention_true_positives}/{total_abstention_cases})")
        print(f"  Mean CPU Inference Latency per Item:   {mean_lat:.2f} ms")

    return summary_metrics


def run_benchmark_comparison(benchmark_path: Path, output_dir: Path) -> None:
    """Run side-by-side comparison between offline feature hashing and pretrained neural embeddings."""
    if not benchmark_path.is_file():
        raise FileNotFoundError(f"Benchmark file not found at: {benchmark_path}")

    raw_data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    print("=" * 80)
    print("  SETU-NETRA: Module 4 Semantic Understanding Backend Comparison")
    print("=" * 80)
    print(f"Held-Out Benchmark Dataset: {benchmark_path} ({len(raw_data)} cases)")

    # 1. Run Offline Evaluation
    offline_metrics = evaluate_single_backend("offline", raw_data, output_dir, verbose=True)

    # 2. Run Neural Evaluation
    neural_metrics = evaluate_single_backend("neural", raw_data, output_dir, verbose=True)

    # 3. Print Side-by-Side Comparison Table
    print("\n" + "=" * 80)
    print("  SIDE-BY-SIDE BACKEND PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"  {'Metric':<32} | {'Offline Baseline':<20} | {'Pretrained Neural':<20}")
    print(f"  {'-'*32}-+-{'-'*20}-+-{'-'*20}")
    off_dim = f"{offline_metrics['dimension']} dim"
    neu_dim = f"{neural_metrics['dimension']} dim"
    off_acc = f"{offline_metrics['domain_accuracy']*100:.2f}%"
    neu_acc = f"{neural_metrics['domain_accuracy']*100:.2f}%"
    off_p = f"{offline_metrics['macro_precision']*100:.2f}%"
    neu_p = f"{neural_metrics['macro_precision']*100:.2f}%"
    off_r = f"{offline_metrics['macro_recall']*100:.2f}%"
    neu_r = f"{neural_metrics['macro_recall']*100:.2f}%"
    off_f1 = f"{offline_metrics['macro_f1']*100:.2f}%"
    neu_f1 = f"{neural_metrics['macro_f1']*100:.2f}%"
    off_int = f"{offline_metrics['intent_accuracy']*100:.2f}%"
    neu_int = f"{neural_metrics['intent_accuracy']*100:.2f}%"
    off_abs = f"{offline_metrics['abstention_accuracy']*100:.2f}%"
    neu_abs = f"{neural_metrics['abstention_accuracy']*100:.2f}%"
    off_lat = f"{offline_metrics['mean_latency_ms']:.2f} ms"
    neu_lat = f"{neural_metrics['mean_latency_ms']:.2f} ms"

    print(f"  {'Engine Identifier':<32} | {offline_metrics['engine_name']:<20} | {neural_metrics['engine_name']:<20}")
    print(f"  {'Vector Dimension':<32} | {off_dim:<20} | {neu_dim:<20}")
    print(f"  {'Domain Classification Accuracy':<32} | {off_acc:<20} | {neu_acc:<20}")
    print(f"  {'Macro Precision':<32} | {off_p:<20} | {neu_p:<20}")
    print(f"  {'Macro Recall':<32} | {off_r:<20} | {neu_r:<20}")
    print(f"  {'Macro F1-Score':<32} | {off_f1:<20} | {neu_f1:<20}")
    print(f"  {'Intent Classification Match':<32} | {off_int:<20} | {neu_int:<20}")
    print(f"  {'Abstention / Open-Set Accuracy':<32} | {off_abs:<20} | {neu_abs:<20}")
    print(f"  {'Mean CPU Latency per Item':<32} | {off_lat:<20} | {neu_lat:<20}")
    print("=" * 80)

    # 4. Prompt-Prescribed Target Queries Evaluation
    print("\n" + "=" * 80)
    print("  EXEMPLAR EVALUATION ON REQUIRED PROMPT QUERIES")
    print("=" * 80)
    exemplar_queries = [
        ("How long does this sorting procedure take to finish running on a laptop?", "everyday_complexity"),
        ("Determine the asymptotic bound on the number of elementary operations executed.", "unseen_paraphrase"),
        ("What is the computational complexity of performing convolution on an image of size HxW with a KxK kernel?", "multi_domain_spatial"),
        ("Explain the kernel used in a two-dimensional convolution.", "disambig_image_kernel"),
        ("Explain the kernel of an operating system.", "disambig_os_kernel"),
        ("Compare the time complexity and space complexity of an algorithm.", "comparative_complexity"),
        ("Which dynamic programming algorithm is used for biological DNA sequence alignment?", "interdisciplinary_bio_cs"),
        ("Calculate the relativistic frame-dragging magnetosphere precession around a Kerr black hole.", "unfamiliar_astrophysics"),
        ("What is the best recipe and oven temperature for baking chocolate chip cookies?", "unrelated_everyday_abstain"),
        ("What e the computationa complexit of performing convolution onan imaqe ofsize HxWwitha kernelofsize KxK?", "ocr_corrupted"),
    ]

    off_eng = SemanticUnderstandingEngine(embedding_engine=get_embedding_engine("offline"))
    neu_eng = SemanticUnderstandingEngine(embedding_engine=get_embedding_engine("neural"))

    exemplar_results = []
    for q_text, q_cat in exemplar_queries:
        res_off = off_eng.analyze_text(q_text)
        res_neu = neu_eng.analyze_text(q_text)
        dom_off = res_off.primary_domain or res_off.status
        dom_neu = res_neu.primary_domain or res_neu.status
        score_off = res_off.domains[0].similarity_score if res_off.domains else 0.0
        score_neu = res_neu.domains[0].similarity_score if res_neu.domains else 0.0

        print(f"\nQuery [{q_cat}]:")
        print(f"  \"{q_text}\"")
        print(f"  Offline: {dom_off} (score: {score_off:.3f}, status: {res_off.status})")
        print(f"  Neural:  {dom_neu} (score: {score_neu:.3f}, status: {res_neu.status})")

        exemplar_results.append({
            "query": q_text,
            "category": q_cat,
            "offline": {"domain": dom_off, "score": score_off, "status": res_off.status},
            "neural": {"domain": dom_neu, "score": score_neu, "status": res_neu.status},
        })

    # Save comparison artifact
    output_dir.mkdir(parents=True, exist_ok=True)
    comp_path = output_dir / "backend_comparison_report.json"
    comp_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "held_out_benchmark": str(benchmark_path),
        "offline_backend": offline_metrics,
        "neural_backend": neural_metrics,
        "exemplar_queries": exemplar_results,
    }
    comp_path.write_text(json.dumps(comp_data, indent=2), encoding="utf-8")
    print(f"\n[OK] Backend comparison report persisted to: {comp_path.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate and compare SETU-NETRA semantic backends.")
    parser.add_argument(
        "--backend",
        type=str,
        default="compare",
        choices=["offline", "neural", "auto", "compare"],
        help="Backend to evaluate: 'offline', 'neural', 'auto', or 'compare' (default: compare).",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default="sample_data/evaluation_benchmark.json",
        help="Path to evaluation benchmark JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save evaluation reports.",
    )
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark)
    output_dir = Path(args.output_dir)

    if args.backend == "compare":
        run_benchmark_comparison(benchmark_path, output_dir)
    else:
        raw_data = json.loads(benchmark_path.read_text(encoding="utf-8"))
        metrics = evaluate_single_backend(args.backend, raw_data, output_dir, verbose=True)
        report_path = output_dir / f"semantic_evaluation_{args.backend}.json"
        report_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"\n[OK] Evaluation report saved to: {report_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
