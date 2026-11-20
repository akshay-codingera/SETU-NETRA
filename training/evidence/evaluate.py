"""
evaluate.py: Rigorous evaluation suite for ER-SP (Evidence Relevance and Sufficiency Predictor).

Compares:
1. Baseline 1: Cosine Retrieval Similarity Threshold (standard RAG thresholding)
2. Baseline 2: Rule-Based Lexical Overlap + Negation Matching Heuristic
3. ER-SP: Proposed Lightweight Epistemic Neural Classifier

Evaluates on:
- Unseen Test Split (test.jsonl - 340 samples, 4 completely held-out topics)
- In-Domain Real-World Benchmark (test_in_domain.jsonl - 12 verified real project samples)

Calculates:
- 5-class Accuracy, Macro F1, Per-class Precision/Recall/F1
- 5x5 Confusion Matrix
- Binary Abstention Metrics (Precision, Recall, F1, Accuracy)
- Expected Calibration Error (ECE, 10 bins)
- CPU Latency (ms per query)
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from setu_netra.evidence.er_sp import (
    ERSPClassifier,
    ERClass,
    compute_pair_interaction_features
)


def compute_ece(confidences: np.ndarray, predictions: np.ndarray, ground_truth: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total_samples = len(confidences)

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(predictions[in_bin] == ground_truth[in_bin])
            avg_confidence_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return float(ece)


class CosineThresholdBaseline:
    """
    Standard RAG Baseline: Uses maximum retrieval cosine similarity.
    Predicts SUFFICIENT if cosine >= threshold, else IRRELEVANT.
    """

    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold

    def predict(self, q_emb: np.ndarray, p_embs: List[np.ndarray]) -> Tuple[str, float, bool]:
        if not p_embs:
            return ERClass.IRRELEVANT, 1.0, True

        cosines = []
        q_norm = np.linalg.norm(q_emb) + 1e-8
        for p in p_embs:
            p_norm = np.linalg.norm(p) + 1e-8
            cos = float(np.dot(q_emb, p) / (q_norm * p_norm))
            cosines.append(cos)

        max_cos = max(cosines) if cosines else 0.0
        if max_cos >= self.threshold:
            # Assumes high semantic similarity implies sufficiency
            return ERClass.SUFFICIENT, max_cos, False
        else:
            return ERClass.IRRELEVANT, 1.0 - max_cos, True


class RuleBasedLexicalBaseline:
    """
    Rule-based Heuristic Baseline:
    Combines Jaccard token overlap with negation and question keyword heuristics.
    """

    NEGATIONS = {"not", "no", "never", "none", "neither", "nor", "cannot", "n't", "false", "prohibit"}

    def __init__(self, sim_thresh_irrel: float = 0.15, sim_thresh_suff: float = 0.45):
        self.sim_thresh_irrel = sim_thresh_irrel
        self.sim_thresh_suff = sim_thresh_suff

    def _jaccard(self, s1: str, s2: str) -> float:
        w1 = set(s1.lower().split())
        w2 = set(s2.lower().split())
        if not w1 or not w2:
            return 0.0
        return len(w1.intersection(w2)) / len(w1.union(w2))

    def predict(self, question: str, passages: List[str]) -> Tuple[str, float, bool]:
        if not passages:
            return ERClass.IRRELEVANT, 1.0, True

        combined_p = " ".join(passages).lower()
        q_low = question.lower()
        sim = self._jaccard(question, combined_p)

        # Check for speculative/unverifiable markers
        speculative_markers = ["will", "future", "ever", "most", "beautiful", "cleanest", "indefinitely", "by 20"]
        if any(marker in q_low for marker in speculative_markers):
            return ERClass.UNVERIFIABLE, 0.65, True

        # Check for negation mismatch
        q_has_neg = any(w in q_low.split() for w in self.NEGATIONS)
        p_has_neg = any(w in combined_p.split() for w in self.NEGATIONS)
        if q_has_neg != p_has_neg and sim >= 0.25:
            return ERClass.CONTRADICTORY, 0.70, True

        if sim < self.sim_thresh_irrel:
            return ERClass.IRRELEVANT, 0.80, True
        elif sim >= self.sim_thresh_suff:
            return ERClass.SUFFICIENT, sim, False
        else:
            return ERClass.PARTIALLY_SUFFICIENT, 0.60, True


def run_evaluation(
    model_checkpoint: str = "models/evidence/er_sp.pt",
    splits_dir: str = "training/datasets/SETU-ER/splits",
    cache_path: str = "training/evidence/embedding_cache.pt",
    output_report_path: str = "models/evidence/evaluation_results.json"
) -> Dict[str, Any]:
    print("=" * 70)
    print("SETU-NETRA: ER-SP Milestone R2 Evaluation Suite")
    print("=" * 70)

    # 1. Load Embeddings Cache
    emb_cache = torch.load(cache_path, map_location="cpu", weights_only=False)
    zero_vec = np.zeros(384, dtype=np.float32)

    # 2. Load ER-SP Model
    device = "cpu"
    checkpoint = torch.load(model_checkpoint, map_location=device, weights_only=True)
    cfg = checkpoint.get("config", {})
    model = ERSPClassifier(
        interaction_dim=cfg.get("model", {}).get("interaction_dim", 1537),
        proj_dim=cfg.get("model", {}).get("proj_dim", 256),
        hidden_dim=cfg.get("model", {}).get("hidden_dim", 128),
        num_classes=cfg.get("model", {}).get("num_classes", 5)
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Loaded ER-SP checkpoint (Epoch {checkpoint.get('epoch', '?')}) with {total_params:,} parameters.")

    # 3. Instantiate Baselines
    cosine_baseline = CosineThresholdBaseline(threshold=0.55)
    rule_baseline = RuleBasedLexicalBaseline()

    # 4. Evaluation Datasets
    eval_splits = {
        "test_unseen_topics": os.path.join(splits_dir, "test.jsonl"),
        "test_in_domain": os.path.join(splits_dir, "test_in_domain.jsonl")
    }

    full_results = {
        "model_checkpoint": model_checkpoint,
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": total_params,
        "evaluations": {}
    }

    for split_key, split_path in eval_splits.items():
        print(f"\n--- Evaluating Split: {split_key} ({split_path}) ---")
        records = []
        with open(split_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        print(f"Loaded {len(records)} test samples.")

        # Ground truths
        true_labels = [r["sufficiency_label"] for r in records]
        true_ids = [r["label_id"] for r in records]
        true_abstain = [bool(r.get("is_abstention_expected", r["label_id"] != 0)) for r in records]

        # Containers for predictions
        preds_ersp = []
        confs_ersp = []
        abstain_ersp = []
        latencies_ersp = []

        preds_cos = []
        confs_cos = []
        abstain_cos = []

        preds_rule = []
        confs_rule = []
        abstain_rule = []

        for r in records:
            q_text = r["question"].strip()
            p_texts = [p.strip() for p in r.get("passages", [""])]

            q_emb = emb_cache.get(q_text, zero_vec)
            p_embs = [emb_cache.get(p, zero_vec) for p in p_texts]

            # 1. Cosine Baseline
            lbl_cos, conf_cos, abs_cos = cosine_baseline.predict(q_emb, p_embs)
            preds_cos.append(lbl_cos)
            confs_cos.append(conf_cos)
            abstain_cos.append(abs_cos)

            # 2. Rule Baseline
            lbl_rule, conf_rule, abs_rule = rule_baseline.predict(q_text, p_texts)
            preds_rule.append(lbl_rule)
            confs_rule.append(conf_rule)
            abstain_rule.append(abs_rule)

            # 3. ER-SP Model
            t0 = time.perf_counter()
            feat_list = [compute_pair_interaction_features(q_emb, p) for p in p_embs]
            interaction_tensor = torch.tensor(np.asarray([feat_list]), dtype=torch.float32, device=device)
            with torch.no_grad():
                logits = model(interaction_tensor)
                probs = F.softmax(logits, dim=-1)[0].cpu().numpy()
            t_lat = (time.perf_counter() - t0) * 1000.0  # ms
            latencies_ersp.append(t_lat)

            pred_id = int(np.argmax(probs))
            pred_lbl = ERClass.ID_TO_LABEL[pred_id]
            pred_conf = float(probs[pred_id])
            preds_ersp.append(pred_lbl)
            confs_ersp.append(pred_conf)
            # Abstain if not SUFFICIENT or conf < 0.50
            abstain_ersp.append(bool(pred_id != 0 or pred_conf < 0.50))

        # Compute Metrics
        def compute_split_metrics(pred_labels, confs, abstain_preds):
            pred_ids = [ERClass.LABEL_TO_ID.get(l, 3) for l in pred_labels]
            acc = float(accuracy_score(true_ids, pred_ids))
            prec, rec, f1, _ = precision_recall_fscore_support(true_ids, pred_ids, average="macro", zero_division=0)

            # Per-class metrics
            per_class = {}
            p_c, r_c, f_c, sup = precision_recall_fscore_support(true_ids, pred_ids, average=None, labels=list(range(5)), zero_division=0)
            for cid in range(5):
                cname = ERClass.ID_TO_LABEL[cid]
                per_class[cname] = {
                    "precision": float(p_c[cid]),
                    "recall": float(r_c[cid]),
                    "f1": float(f_c[cid]),
                    "support": int(sup[cid])
                }

            # Abstention metrics (binary)
            abs_acc = float(accuracy_score(true_abstain, abstain_preds))
            abs_p, abs_r, abs_f1, _ = precision_recall_fscore_support(true_abstain, abstain_preds, average="binary", zero_division=0)

            # ECE
            ece = compute_ece(np.array(confs), np.array(pred_ids), np.array(true_ids), n_bins=10)

            # Confusion Matrix
            cm = confusion_matrix(true_ids, pred_ids, labels=list(range(5))).tolist()

            return {
                "accuracy": acc,
                "macro_precision": float(prec),
                "macro_recall": float(rec),
                "macro_f1": float(f1),
                "abstention_accuracy": abs_acc,
                "abstention_precision": float(abs_p),
                "abstention_recall": float(abs_r),
                "abstention_f1": float(abs_f1),
                "ece": ece,
                "per_class": per_class,
                "confusion_matrix": cm
            }

        metrics_ersp = compute_split_metrics(preds_ersp, confs_ersp, abstain_ersp)
        metrics_ersp["latency_ms_mean"] = float(np.mean(latencies_ersp))
        metrics_ersp["latency_ms_p95"] = float(np.percentile(latencies_ersp, 95))

        metrics_cos = compute_split_metrics(preds_cos, confs_cos, abstain_cos)
        metrics_rule = compute_split_metrics(preds_rule, confs_rule, abstain_rule)

        split_summary = {
            "samples": len(records),
            "ER_SP": metrics_ersp,
            "Baseline_Cosine_Threshold": metrics_cos,
            "Baseline_Rule_Lexical": metrics_rule
        }
        full_results["evaluations"][split_key] = split_summary

        print(f"\nResults on {split_key}:")
        print(f"  [Baseline 1: Cosine Thresh] Acc: {metrics_cos['accuracy']*100:.2f}% | Macro F1: {metrics_cos['macro_f1']:.4f} | Abstain F1: {metrics_cos['abstention_f1']:.4f} | ECE: {metrics_cos['ece']:.4f}")
        print(f"  [Baseline 2: Rule Heuristic] Acc: {metrics_rule['accuracy']*100:.2f}% | Macro F1: {metrics_rule['macro_f1']:.4f} | Abstain F1: {metrics_rule['abstention_f1']:.4f} | ECE: {metrics_rule['ece']:.4f}")
        print(f"  [Proposed: ER-SP Model]     Acc: {metrics_ersp['accuracy']*100:.2f}% | Macro F1: {metrics_ersp['macro_f1']:.4f} | Abstain F1: {metrics_ersp['abstention_f1']:.4f} | ECE: {metrics_ersp['ece']:.4f} | Latency: {metrics_ersp['latency_ms_mean']:.3f}ms")

    # Save to disk
    with open(output_report_path, "w", encoding="utf-8") as fp:
        json.dump(full_results, fp, indent=2)

    print("\n" + "=" * 70)
    print(f"Evaluation complete. Full report written to: {output_report_path}")
    print("=" * 70)
    return full_results


if __name__ == "__main__":
    run_evaluation()
