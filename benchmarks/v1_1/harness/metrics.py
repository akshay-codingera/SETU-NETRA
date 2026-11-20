"""
metrics.py: Formal evaluation metrics and statistical bootstrap routines for SETU-NETRA V1.1.
Calculates Exact Match, Token F1, Citation Precision, Retrieval Recall@K, MRR, nDCG@K,
latency percentiles (P50, P95, P99), and bootstrapped 95% confidence intervals.
"""

import math
import re
import string
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np


def normalize_text(text: str) -> str:
    """Lowercases text, strips punctuation, articles, and extra whitespace."""
    text = text.lower()
    # Strip punctuation
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    # Strip articles
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    # Strip whitespace
    return " ".join(text.split())


def compute_exact_match(prediction: str, ground_truth: str) -> float:
    """Binary indicator of whether normalized prediction matches normalized ground truth."""
    return 1.0 if normalize_text(prediction) == normalize_text(ground_truth) else 0.0


def compute_token_f1(prediction: str, ground_truth: str) -> Tuple[float, float, float]:
    """Calculate token-level precision, recall, and F1 between prediction and ground truth.

    Returns:
        (precision, recall, f1)
    """
    pred_tokens = normalize_text(prediction).split()
    gold_tokens = normalize_text(ground_truth).split()

    if not pred_tokens and not gold_tokens:
        return 1.0, 1.0, 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0, 0.0, 0.0

    common_tokens = set(pred_tokens) & set(gold_tokens)
    if not common_tokens:
        return 0.0, 0.0, 0.0

    # Token overlap count with multiplicity
    pred_counter = {t: pred_tokens.count(t) for t in set(pred_tokens)}
    gold_counter = {t: gold_tokens.count(t) for t in set(gold_tokens)}
    overlap_count = sum(min(pred_counter[t], gold_counter[t]) for t in common_tokens)

    prec = overlap_count / len(pred_tokens)
    rec = overlap_count / len(gold_tokens)
    f1 = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return float(prec), float(rec), float(f1)


def compute_citation_precision(citations: Sequence[Dict[str, Any]], expected_blocks: Sequence[int]) -> float:
    """Measure proportion of generated citations that match expected passage blocks."""
    if not citations:
        return 1.0 if not expected_blocks else 0.0

    valid_count = 0
    for cite in citations:
        block_id = cite.get("block_id")
        if block_id is not None and int(block_id) in expected_blocks:
            valid_count += 1
    return float(valid_count / len(citations))


def compute_retrieval_metrics(
    retrieved_block_ids: Sequence[int],
    expected_block_ids: Sequence[int],
    k_values: Tuple[int, ...] = (1, 3, 5),
) -> Dict[str, float]:
    """Calculate passage-level Recall@K, Precision@K, MRR, and nDCG@K."""
    results = {}
    if not expected_block_ids:
        # If no expected blocks (unsupported query)
        for k in k_values:
            results[f"recall@{k}"] = 1.0 if not retrieved_block_ids else 0.0
            results[f"precision@{k}"] = 1.0 if not retrieved_block_ids else 0.0
        results["mrr"] = 1.0 if not retrieved_block_ids else 0.0
        results["ndcg@3"] = 1.0 if not retrieved_block_ids else 0.0
        return results

    gold_set = set(int(b) for b in expected_block_ids)

    # Precision and Recall at K
    for k in k_values:
        top_k = retrieved_block_ids[:k]
        hits = len(set(int(b) for b in top_k) & gold_set)
        results[f"recall@{k}"] = float(hits / len(gold_set))
        results[f"precision@{k}"] = float(hits / k) if k > 0 else 0.0

    # Mean Reciprocal Rank (MRR)
    mrr = 0.0
    for rank, b in enumerate(retrieved_block_ids, start=1):
        if int(b) in gold_set:
            mrr = 1.0 / rank
            break
    results["mrr"] = float(mrr)

    # nDCG at 3
    dcg = 0.0
    for idx, b in enumerate(retrieved_block_ids[:3]):
        rel = 1.0 if int(b) in gold_set else 0.0
        dcg += (2.0**rel - 1.0) / math.log2(idx + 2.0)

    # Ideal DCG for min(len(gold_set), 3)
    idcg = sum((2.0**1.0 - 1.0) / math.log2(i + 2.0) for i in range(min(len(gold_set), 3)))
    results["ndcg@3"] = float(dcg / idcg) if idcg > 0 else 0.0

    return results


def bootstrap_confidence_interval(
    values: Sequence[float],
    statistic_fn=np.mean,
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    random_seed: int = 42,
) -> Tuple[float, float]:
    """Compute non-parametric bootstrap confidence interval for a given statistic."""
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0
    if len(arr) == 1:
        return float(arr[0]), float(arr[0])

    rng = np.random.default_rng(random_seed)
    boot_stats = np.empty(n_resamples)
    n = len(arr)

    for i in range(n_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        boot_stats[i] = statistic_fn(sample)

    alpha = (1.0 - confidence_level) / 2.0
    lower = float(np.percentile(boot_stats, 100.0 * alpha))
    upper = float(np.percentile(boot_stats, 100.0 * (1.0 - alpha)))
    return lower, upper


def compute_percentiles_with_ci(
    latencies: Sequence[float],
    percentiles: Tuple[float, ...] = (50.0, 95.0, 99.0),
    n_resamples: int = 1000,
    random_seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Compute exact latency percentiles along with bootstrapped 95% confidence intervals."""
    arr = np.array(latencies, dtype=float)
    results = {}
    if len(arr) == 0:
        for p in percentiles:
            tag = f"p{int(p)}"
            results[tag] = {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
        return results

    for p in percentiles:
        tag = f"p{int(p)}"
        val = float(np.percentile(arr, p))
        lower, upper = bootstrap_confidence_interval(
            arr,
            statistic_fn=lambda x: np.percentile(x, p),
            n_resamples=n_resamples,
            confidence_level=0.95,
            random_seed=random_seed,
        )
        results[tag] = {
            "value": round(val, 2),
            "ci_lower": round(lower, 2),
            "ci_upper": round(upper, 2),
        }

    return results
