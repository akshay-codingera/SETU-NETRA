"""
calculator.py: Scientific metrics calculation engine for SETU-NETRA benchmarks.

Why this file exists:
Provides mathematical and statistical metrics calculation for:
- Latency percentiles (Mean, P50, P90, P95, P99, Min, Max, StdDev, 95% Confidence Intervals)
- Traffic scheduling metrics (Throughput, Queue Wait, Utilization, Overhead)
- Model routing classification metrics (Confusion Matrix, Precision, Recall, F1, Accuracy)
- Information retrieval metrics (Recall@K, Precision@K, Mean Reciprocal Rank - MRR)
- Question Answering quality metrics (Exact Match, Token F1, Citation Precision & Completeness)
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def compute_statistical_summary(values: List[float]) -> Dict[str, float]:
    """Compute comprehensive statistical metrics and percentiles from a list of floats."""
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std_dev": 0.0,
            "ci95_lower": 0.0,
            "ci95_upper": 0.0,
        }

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mean_val = sum(sorted_vals) / n

    # Variance and standard deviation
    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in sorted_vals) / (n - 1)
        std_dev = math.sqrt(variance)
    else:
        variance = 0.0
        std_dev = 0.0

    # 95% Confidence Interval for the mean (using normal z=1.96 approximation for n >= 30, t-distribution approx for small n)
    z = 1.96 if n >= 30 else 2.262 if n >= 10 else 2.571
    margin_error = z * (std_dev / math.sqrt(n)) if n > 0 else 0.0

    p50 = sorted_vals[int(0.50 * n)]
    p90 = sorted_vals[min(int(0.90 * n), n - 1)]
    p95 = sorted_vals[min(int(0.95 * n), n - 1)]
    p99 = sorted_vals[min(int(0.99 * n), n - 1)]

    return {
        "count": n,
        "mean": round(mean_val, 2),
        "p50": round(p50, 2),
        "p90": round(p90, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
        "std_dev": round(std_dev, 2),
        "ci95_lower": round(max(0.0, mean_val - margin_error), 2),
        "ci95_upper": round(mean_val + margin_error, 2),
    }


def compute_classification_metrics(
    ground_truth: List[str],
    predictions: List[str],
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calculate multiclass confusion matrix, per-class precision/recall/F1, and overall accuracy."""
    if len(ground_truth) != len(predictions):
        raise ValueError("ground_truth and predictions must have identical lengths.")

    all_labels = labels or sorted(list(set(ground_truth) | set(predictions)))
    label_to_idx = {l: i for i, l in enumerate(all_labels)}
    num_labels = len(all_labels)

    # Confusion matrix: rows = true, cols = pred
    matrix = [[0 for _ in range(num_labels)] for _ in range(num_labels)]
    for true_val, pred_val in zip(ground_truth, predictions):
        t_idx = label_to_idx.get(true_val)
        p_idx = label_to_idx.get(pred_val)
        if t_idx is not None and p_idx is not None:
            matrix[t_idx][p_idx] += 1

    per_class: Dict[str, Dict[str, float]] = {}
    total_correct = 0

    for idx, label in enumerate(all_labels):
        tp = matrix[idx][idx]
        total_correct += tp
        fn = sum(matrix[idx][j] for j in range(num_labels) if j != idx)
        fp = sum(matrix[i][idx] for i in range(num_labels) if i != idx)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": tp + fn,
        }

    overall_acc = (total_correct / len(ground_truth)) if ground_truth else 0.0
    macro_f1 = (sum(m["f1_score"] for m in per_class.values()) / num_labels) if num_labels > 0 else 0.0

    return {
        "accuracy": round(overall_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "total_samples": len(ground_truth),
        "labels": all_labels,
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def compute_retrieval_ranking_metrics(
    retrieved_doc_ids_list: List[List[str]],
    relevant_doc_ids_list: List[Set[str]],
    k_values: Tuple[int, ...] = (1, 3, 5, 10),
) -> Dict[str, float]:
    """Calculate Recall@K, Precision@K, and Mean Reciprocal Rank (MRR)."""
    if len(retrieved_doc_ids_list) != len(relevant_doc_ids_list):
        raise ValueError("Retrieved lists and relevant sets must have matching lengths.")

    num_queries = len(retrieved_doc_ids_list)
    if num_queries == 0:
        return {f"recall@{k}": 0.0 for k in k_values} | {f"precision@{k}": 0.0 for k in k_values} | {"mrr": 0.0}

    reciprocal_ranks: List[float] = []
    recall_at_k: Dict[int, List[float]] = {k: [] for k in k_values}
    precision_at_k: Dict[int, List[float]] = {k: [] for k in k_values}

    for retrieved, relevant in zip(retrieved_doc_ids_list, relevant_doc_ids_list):
        if not relevant:
            continue

        # MRR calculation
        rr = 0.0
        for rank, doc_id in enumerate(retrieved, start=1):
            if doc_id in relevant:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # Recall@K and Precision@K
        for k in k_values:
            top_k = retrieved[:k]
            hits = len(set(top_k) & relevant)
            prec = hits / k if k > 0 else 0.0
            rec = hits / len(relevant) if len(relevant) > 0 else 0.0
            precision_at_k[k].append(prec)
            recall_at_k[k].append(rec)

    metrics = {
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0, 4),
    }
    for k in k_values:
        p_list = precision_at_k[k]
        r_list = recall_at_k[k]
        metrics[f"precision@{k}"] = round(sum(p_list) / len(p_list) if p_list else 0.0, 4)
        metrics[f"recall@{k}"] = round(sum(r_list) / len(r_list) if r_list else 0.0, 4)

    return metrics


def normalize_text_tokens(text: str) -> List[str]:
    """Tokenize and normalize text for exact match and token F1."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.strip().split()
    return tokens


def compute_qa_token_f1_and_em(
    prediction: str,
    ground_truth: str,
) -> Tuple[float, float]:
    """Calculate token-level Exact Match (EM: 0.0 or 1.0) and Token F1 (0.0 to 1.0)."""
    pred_tokens = normalize_text_tokens(prediction)
    gold_tokens = normalize_text_tokens(ground_truth)

    if not pred_tokens and not gold_tokens:
        return 1.0, 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0, 0.0

    # Exact Match
    exact_match = 1.0 if (" ".join(pred_tokens) == " ".join(gold_tokens)) else 0.0

    # Token F1
    common_tokens = set(pred_tokens) & set(gold_tokens)
    if not common_tokens:
        return exact_match, 0.0

    num_same = sum(min(pred_tokens.count(tok), gold_tokens.count(tok)) for tok in common_tokens)
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return exact_match, round(f1, 4)


def compute_citation_metrics(
    extracted_citations: List[Dict[str, Any]],
    expected_evidence_citations: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Evaluate citation precision and completeness against ground-truth evidence coordinates.

    Citations match if doc_id matches and page matches (and block matches if specified).
    """
    if not expected_evidence_citations:
        # If no citation was required
        prec = 1.0 if not extracted_citations else 0.5
        comp = 1.0
        return {"citation_precision": prec, "citation_completeness": comp}

    if not extracted_citations:
        return {"citation_precision": 0.0, "citation_completeness": 0.0}

    def cite_key(c: Dict[str, Any]) -> str:
        doc = str(c.get("doc_id", c.get("document_id", ""))).strip().lower()
        page = str(c.get("page_number", c.get("page", ""))).strip()
        block = str(c.get("block_index", c.get("block_id", ""))).strip()
        return f"{doc}:p{page}:b{block}"

    def loose_key(c: Dict[str, Any]) -> str:
        doc = str(c.get("doc_id", c.get("document_id", ""))).strip().lower()
        page = str(c.get("page_number", c.get("page", ""))).strip()
        return f"{doc}:p{page}"

    expected_keys = {cite_key(c) for c in expected_evidence_citations}
    expected_loose = {loose_key(c) for c in expected_evidence_citations}

    true_positive = 0
    for c in extracted_citations:
        if cite_key(c) in expected_keys or loose_key(c) in expected_loose:
            true_positive += 1

    precision = true_positive / len(extracted_citations) if extracted_citations else 0.0
    completeness = min(1.0, true_positive / len(expected_evidence_citations)) if expected_evidence_citations else 1.0

    return {
        "citation_precision": round(precision, 4),
        "citation_completeness": round(completeness, 4),
    }
