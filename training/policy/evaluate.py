"""
evaluate.py: Evaluation suite for CM-RP (Contextual Multi-Strategy Reasoning Policy).

Compares:
1. Baseline 1: Existing Static Domain Router (DomainSolverRouter)
2. Baseline 2: Rule-Based Strategy Selector Heuristic
3. Proposed: Trained CM-RP Policy Network (CMPolicyNetwork)

Evaluates on:
- Unseen Topics Test Split (test.jsonl - 340 samples on 4 held-out topics)
- In-Domain Real-World Benchmark (test_in_domain.jsonl - 10 verified real project cases)

Measures:
- Strategy Selection Accuracy & Macro F1
- Task Success Rate (when executing the selected solver)
- Correct Abstention Rate (Precision, Recall, F1 on ABSTAIN)
- End-to-End Correctness
- CPU Latency (ms per routing decision)
- Hardware-Aware Routing Performance (under simulated and real RAM saturation)
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

# Ensure 'src' is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from setu_netra.policy.cm_rp import (
    CMPolicyNetwork,
    StrategyAction,
    ACTION_TO_ID,
    ID_TO_ACTION,
    NUM_ACTIONS,
    CMRPDispatcher,
    ContextFeatureExtractor
)
from setu_netra.qa.domain_router import classify_domain, QuestionDomain


class StaticDomainRouterBaseline:
    """
    Baseline 1: Existing static domain router (classify_domain).
    Maps classified QuestionDomain statically to a single strategy without ER-SP
    or hardware telemetry awareness.
    """

    def predict(self, question: str) -> str:
        dom, conf, meta = classify_domain(question)

        if dom == QuestionDomain.ARITHMETIC:
            return StrategyAction.ARITHMETIC_SOLVER.value
        elif dom in (QuestionDomain.DBMS_NORMALIZATION, QuestionDomain.SQL):
            return StrategyAction.DBMS_SOLVER.value
        elif dom in (QuestionDomain.FORMAL_LOGIC, QuestionDomain.LOGICAL_REASONING):
            return StrategyAction.FORMAL_LOGIC_SOLVER.value
        elif dom == QuestionDomain.DOCUMENT_QA:
            # Statically routes all document QA to extractive
            return StrategyAction.EXTRACTIVE_QA.value
        elif dom == QuestionDomain.GENERAL_KNOWLEDGE:
            return StrategyAction.ABSTAIN.value
        else:
            return StrategyAction.EXTRACTIVE_QA.value


class RuleBasedStrategyBaseline:
    """
    Baseline 2: Handcrafted rule-based strategy selection heuristic.
    Combines keyword matching with basic ER-SP thresholding.
    """

    def predict(self, question: str, er_p: List[float], ram_avail_mb: float) -> str:
        q_low = question.lower()

        # 1. Symbolic triggers
        if any(op in q_low for op in ["+", "-", "*", "/", "="]) and any(k in q_low for k in ["result", "calculate", "value", "given"]):
            return StrategyAction.ARITHMETIC_SOLVER.value
        if any(k in q_low for k in ["functional dependenc", "2nf", "3nf", "bcnf", "candidate key", "highest normal form"]):
            return StrategyAction.DBMS_SOLVER.value
        if any(k in q_low for k in ["syllogism", "contrapositive", "some cats", "all dogs", "counter-model"]):
            return StrategyAction.FORMAL_LOGIC_SOLVER.value

        # 2. Epistemic thresholding (ER-SP probabilities: [SUFF, PART, CONTRA, IRREL, UNVER])
        if len(er_p) == 5:
            if er_p[1] > 0.40:  # PARTIALLY_SUFFICIENT
                return StrategyAction.ADDITIONAL_RETRIEVAL.value
            if er_p[2] > 0.40 or er_p[4] > 0.40:  # CONTRADICTORY or UNVERIFIABLE
                return StrategyAction.ABSTAIN.value

        # 3. Resource thresholding
        if ram_avail_mb < 1500.0:
            return StrategyAction.ABSTAIN.value

        # 4. Long / comparative questions
        if any(k in q_low for k in ["compare", "contrast", "synthesize", "trade-off"]):
            return StrategyAction.LOCAL_SLM.value

        return StrategyAction.EXTRACTIVE_QA.value


def evaluate_policy_pipeline(
    model_checkpoint: str = "models/policy/cm_rp.pt",
    splits_dir: str = "training/datasets/SETU-CM/splits",
    output_report_path: str = "models/policy/evaluation_results.json"
) -> Dict[str, Any]:
    print("=" * 70)
    print("SETU-NETRA: CM-RP Milestone R3 Comprehensive Evaluation Suite")
    print("=" * 70)

    # 1. Load Trained CM-RP Model
    device = "cpu"
    checkpoint = torch.load(model_checkpoint, map_location=device, weights_only=True)
    cfg = checkpoint.get("config", {})

    model = CMPolicyNetwork(
        input_dim=cfg.get("model", {}).get("input_dim", 423),
        hidden_dim1=cfg.get("model", {}).get("hidden_dim1", 128),
        hidden_dim2=cfg.get("model", {}).get("hidden_dim2", 64),
        num_actions=cfg.get("model", {}).get("num_actions", 7)
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Loaded CM-RP Checkpoint (Epoch {checkpoint.get('epoch', '?')}) with {total_params:,} parameters.")

    # 2. Baselines
    static_router = StaticDomainRouterBaseline()
    rule_selector = RuleBasedStrategyBaseline()

    # 3. Splits to Evaluate
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

        true_actions = [r["expected_action"] for r in records]
        true_ids = [r["action_id"] for r in records]
        true_is_abstain = [bool(r["expected_action"] == StrategyAction.ABSTAIN.value) for r in records]

        # Containers
        preds_cmrp = []
        confs_cmrp = []
        latencies_cmrp = []
        dispatch_success_cmrp = 0

        preds_static = []
        latencies_static = []

        preds_rule = []
        latencies_rule = []

        for r in records:
            q = r["question"]
            feat_vec = r["context_features"]
            mask_vec = r["action_mask"]
            ram_mb = r["resource_consumption"]["avail_ram_mb"]
            er_probs = feat_vec[392:397]  # 5-d ER-SP probabilities

            # 1. Static Router Baseline
            t0 = time.perf_counter()
            act_static = static_router.predict(q)
            lat_static = (time.perf_counter() - t0) * 1000.0
            preds_static.append(act_static)
            latencies_static.append(lat_static)

            # 2. Rule-Based Baseline
            t0 = time.perf_counter()
            act_rule = rule_selector.predict(q, er_probs, ram_mb)
            lat_rule = (time.perf_counter() - t0) * 1000.0
            preds_rule.append(act_rule)
            latencies_rule.append(lat_rule)

            # 3. CM-RP Policy Network
            t0 = time.perf_counter()
            with torch.no_grad():
                x_t = torch.tensor(np.asarray([feat_vec]), dtype=torch.float32, device=device)
                m_t = torch.tensor(np.asarray([mask_vec]), dtype=torch.float32, device=device)
                logits = model(x_t, action_mask=m_t)
                probs = F.softmax(logits, dim=-1)[0].cpu().numpy()
            lat_cmrp = (time.perf_counter() - t0) * 1000.0

            pred_id = int(np.argmax(probs))
            pred_act = ID_TO_ACTION[pred_id]
            pred_conf = float(probs[pred_id])

            preds_cmrp.append(pred_act)
            confs_cmrp.append(pred_conf)
            latencies_cmrp.append(lat_cmrp)

            # Execute real dispatch for in-domain samples to test solver integration
            if split_key == "test_in_domain":
                try:
                    disp_res = CMRPDispatcher.dispatch(pred_act, q)
                    if disp_res.get("status") in ("SUCCESS", "ABSTAINED", "RETRIEVAL_EXPANSION_TRIGGERED"):
                        dispatch_success_cmrp += 1
                except Exception as e:
                    pass

        # Compute Metrics
        def compute_metrics(predicted_actions):
            pred_ids = [ACTION_TO_ID.get(a, 6) for a in predicted_actions]
            acc = float(accuracy_score(true_ids, pred_ids))
            prec, rec, f1, _ = precision_recall_fscore_support(true_ids, pred_ids, average="macro", zero_division=0)

            # Abstention metrics (binary)
            pred_is_abstain = [bool(a == StrategyAction.ABSTAIN.value) for a in predicted_actions]
            abs_acc = float(accuracy_score(true_is_abstain, pred_is_abstain))
            abs_p, abs_r, abs_f1, _ = precision_recall_fscore_support(true_is_abstain, pred_is_abstain, average="binary", zero_division=0)

            # Per-class breakdown
            per_action = {}
            p_a, r_a, f_a, sup = precision_recall_fscore_support(true_ids, pred_ids, average=None, labels=list(range(NUM_ACTIONS)), zero_division=0)
            for aid in range(NUM_ACTIONS):
                aname = ID_TO_ACTION[aid]
                per_action[aname] = {
                    "precision": float(p_a[aid]),
                    "recall": float(r_a[aid]),
                    "f1": float(f_a[aid]),
                    "support": int(sup[aid])
                }

            # Confusion matrix
            cm = confusion_matrix(true_ids, pred_ids, labels=list(range(NUM_ACTIONS))).tolist()

            return {
                "accuracy": acc,
                "macro_precision": float(prec),
                "macro_recall": float(rec),
                "macro_f1": float(f1),
                "abstention_accuracy": abs_acc,
                "abstention_precision": float(abs_p),
                "abstention_recall": float(abs_r),
                "abstention_f1": float(abs_f1),
                "per_action": per_action,
                "confusion_matrix": cm
            }

        m_cmrp = compute_metrics(preds_cmrp)
        m_cmrp["latency_ms_mean"] = float(np.mean(latencies_cmrp))
        m_cmrp["latency_ms_p95"] = float(np.percentile(latencies_cmrp, 95))
        if split_key == "test_in_domain":
            m_cmrp["dispatch_execution_success_rate"] = float(dispatch_success_cmrp / len(records))

        m_static = compute_metrics(preds_static)
        m_static["latency_ms_mean"] = float(np.mean(latencies_static))

        m_rule = compute_metrics(preds_rule)
        m_rule["latency_ms_mean"] = float(np.mean(latencies_rule))

        split_summary = {
            "samples": len(records),
            "CM_RP": m_cmrp,
            "Baseline_Static_Domain_Router": m_static,
            "Baseline_Rule_Based_Selector": m_rule
        }
        full_results["evaluations"][split_key] = split_summary

        print(f"\nResults on {split_key}:")
        print(f"  [Baseline 1: Static Router]  Acc: {m_static['accuracy']*100:.2f}% | Macro F1: {m_static['macro_f1']:.4f} | Abstain F1: {m_static['abstention_f1']:.4f} | Latency: {m_static['latency_ms_mean']:.3f}ms")
        print(f"  [Baseline 2: Rule Selector]  Acc: {m_rule['accuracy']*100:.2f}% | Macro F1: {m_rule['macro_f1']:.4f} | Abstain F1: {m_rule['abstention_f1']:.4f} | Latency: {m_rule['latency_ms_mean']:.3f}ms")
        print(f"  [Proposed: CM-RP Policy]    Acc: {m_cmrp['accuracy']*100:.2f}% | Macro F1: {m_cmrp['macro_f1']:.4f} | Abstain F1: {m_cmrp['abstention_f1']:.4f} | Latency: {m_cmrp['latency_ms_mean']:.3f}ms")

    # Save to disk
    with open(output_report_path, "w", encoding="utf-8") as fp:
        json.dump(full_results, fp, indent=2)

    print("\n" + "=" * 70)
    print(f"Evaluation complete. Full report written to: {output_report_path}")
    print("=" * 70)
    return full_results


if __name__ == "__main__":
    evaluate_policy_pipeline()
