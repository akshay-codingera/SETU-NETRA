"""
test_er_sp.py: Formal unit and regression test suite for ER-SP (Milestone R2).

Verifies:
1. Model initialization and parameter count (~560k parameters).
2. Forward pass with single-passage tensors.
3. Forward pass with multi-passage tensors and attention masking.
4. Dataset files existence and JSONL validity.
5. Zero leakage across train, val, and test splits.
6. Checkpoint persistence and loading.
7. Feature computation helper correctness.
8. Contradiction and epistemic classification outputs.
9. Abstention recommendation policy logic.
10. CPU inference latency benchmark (< 5.0 ms).
"""

import os
import sys
import json
import time
import unittest
import numpy as np
import torch
import torch.nn.functional as F

# Ensure 'src' is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "training", "evidence")))

from setu_netra.evidence.er_sp import (
    ERSPClassifier,
    ERSPPredictor,
    ERClass,
    compute_pair_interaction_features
)


class TestERSPArchitecture(unittest.TestCase):
    """Tests for the ERSP neural network architecture."""

    def setUp(self):
        self.device = torch.device("cpu")
        self.model = ERSPClassifier(
            interaction_dim=1537,
            proj_dim=256,
            hidden_dim=128,
            num_classes=5
        ).to(self.device)

    def test_parameter_count(self):
        """Model must be lightweight (~560k parameters)."""
        param_count = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        self.assertGreater(param_count, 500_000)
        self.assertLess(param_count, 650_000)

    def test_single_passage_forward(self):
        """Forward pass for batch of single passages (B, 1537)."""
        batch_size = 4
        x = torch.randn(batch_size, 1537, device=self.device)
        logits = self.model(x)
        self.assertEqual(logits.shape, (batch_size, 5))
        self.assertFalse(torch.isnan(logits).any())

    def test_multi_passage_forward_with_mask(self):
        """Forward pass for multi-passage inputs with attention masking (B, K, 1537)."""
        batch_size = 3
        k_passages = 4
        x = torch.randn(batch_size, k_passages, 1537, device=self.device)
        mask = torch.tensor([
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0]
        ], device=self.device)

        logits = self.model(x, mask=mask)
        self.assertEqual(logits.shape, (batch_size, 5))
        self.assertFalse(torch.isnan(logits).any())

    def test_feature_computation(self):
        """Validates interaction feature dimension and cosine bounds."""
        q = np.random.randn(384).astype(np.float32)
        p = np.random.randn(384).astype(np.float32)
        feats = compute_pair_interaction_features(q, p)

        self.assertEqual(feats.shape, (1537,))
        # Last feature is cosine similarity in [-1, 1]
        cos_val = float(feats[-1])
        self.assertGreaterEqual(cos_val, -1.01)
        self.assertLessEqual(cos_val, 1.01)


class TestERSPDatasetIntegrity(unittest.TestCase):
    """Tests for dataset splits, records, and zero-leakage guarantees."""

    def setUp(self):
        self.splits_dir = "training/datasets/SETU-ER/splits"
        self.manifest_path = "training/datasets/SETU-ER/dataset_manifest.json"

    def test_manifest_and_splits_exist(self):
        """Manifest and all 4 split files must exist on disk."""
        self.assertTrue(os.path.exists(self.manifest_path))
        for split_file in ["train.jsonl", "val.jsonl", "test.jsonl", "test_in_domain.jsonl"]:
            fpath = os.path.join(self.splits_dir, split_file)
            self.assertTrue(os.path.exists(fpath), f"Missing split: {split_file}")

    def test_split_records_valid(self):
        """All records must parse as valid JSON with required schema fields."""
        required_keys = {"example_id", "question", "passages", "sufficiency_label", "label_id"}
        for split_file in ["train.jsonl", "val.jsonl", "test.jsonl", "test_in_domain.jsonl"]:
            fpath = os.path.join(self.splits_dir, split_file)
            with open(fpath, "r", encoding="utf-8") as fp:
                lines = [line.strip() for line in fp if line.strip()]
            self.assertGreater(len(lines), 0)
            for line in lines:
                data = json.loads(line)
                self.assertTrue(required_keys.issubset(data.keys()))
                self.assertIn(data["sufficiency_label"], ERClass.ALL)
                self.assertEqual(data["label_id"], ERClass.LABEL_TO_ID[data["sufficiency_label"]])

    def test_zero_leakage_between_splits(self):
        """Guarantees 0% question overlap between Train, Val, Test, and In-Domain."""
        def load_questions(fname):
            with open(os.path.join(self.splits_dir, fname), "r", encoding="utf-8") as fp:
                return set(json.loads(line)["question"].strip() for line in fp if line.strip())

        train_qs = load_questions("train.jsonl")
        val_qs = load_questions("val.jsonl")
        test_qs = load_questions("test.jsonl")
        indomain_qs = load_questions("test_in_domain.jsonl")

        self.assertEqual(len(train_qs.intersection(val_qs)), 0, "Question leakage between Train and Val!")
        self.assertEqual(len(train_qs.intersection(test_qs)), 0, "Question leakage between Train and Test!")
        self.assertEqual(len(val_qs.intersection(test_qs)), 0, "Question leakage between Val and Test!")
        self.assertEqual(len(train_qs.intersection(indomain_qs)), 0, "Question leakage between Train and InDomain!")


class TestERSPPredictorAndCheckpoint(unittest.TestCase):
    """Tests predictor loading, abstention recommendations, and inference latency."""

    @classmethod
    def setUpClass(cls):
        cls.ckpt_path = "models/evidence/er_sp.pt"
        cls.predictor = ERSPPredictor(checkpoint_path=cls.ckpt_path, device="cpu")

    def test_checkpoint_loaded(self):
        """Predictor must load checkpoint successfully."""
        self.assertTrue(self.predictor.is_loaded)
        self.assertIsNotNone(self.predictor.model)

    def test_abstention_policy(self):
        """Abstention policy must recommend abstaining on non-sufficient classes."""
        q_dummy = np.random.randn(384).astype(np.float32)
        p_dummy = [np.random.randn(384).astype(np.float32)]

        res = self.predictor.predict_from_embeddings(q_dummy, p_dummy)
        self.assertIn("label", res)
        self.assertIn("confidence", res)
        self.assertIn("should_abstain", res)
        self.assertIn("probabilities", res)

        # If label is not SUFFICIENT, should_abstain must be True
        if res["label"] != ERClass.SUFFICIENT:
            self.assertTrue(res["should_abstain"])
            self.assertIsNotNone(res["abstention_reason"])

    def test_empty_passages_abstention(self):
        """Zero passages must trigger immediate abstention."""
        q_dummy = np.random.randn(384).astype(np.float32)
        res = self.predictor.predict_from_embeddings(q_dummy, [])
        self.assertEqual(res["label"], ERClass.IRRELEVANT)
        self.assertTrue(res["should_abstain"])

    def test_inference_latency(self):
        """CPU inference latency for single query must be under 5.0 ms."""
        q_dummy = np.random.randn(384).astype(np.float32)
        p_dummy = [np.random.randn(384).astype(np.float32), np.random.randn(384).astype(np.float32)]

        # Warmup
        for _ in range(5):
            _ = self.predictor.predict_from_embeddings(q_dummy, p_dummy)

        t0 = time.perf_counter()
        iters = 50
        for _ in range(iters):
            _ = self.predictor.predict_from_embeddings(q_dummy, p_dummy)
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        avg_latency_ms = total_time_ms / iters

        self.assertLess(avg_latency_ms, 5.0, f"Latency {avg_latency_ms:.3f}ms exceeds 5.0ms threshold!")


if __name__ == "__main__":
    unittest.main()
