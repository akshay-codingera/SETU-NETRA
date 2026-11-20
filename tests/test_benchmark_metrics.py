"""
test_benchmark_metrics.py: Unit tests for statistical, classification, retrieval, and QA metrics.

Tests:
1. compute_statistical_summary (mean, p50, p95, p99, std_dev, 95% confidence intervals).
2. compute_classification_metrics (confusion matrix, precision, recall, F1, accuracy).
3. compute_retrieval_ranking_metrics (Recall@K, Precision@K, MRR).
4. compute_qa_token_f1_and_em (token exact match and harmonic F1).
5. compute_citation_metrics (coordinate matching and completeness).
"""

import math
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.metrics.calculator import (
    compute_citation_metrics,
    compute_classification_metrics,
    compute_qa_token_f1_and_em,
    compute_retrieval_ranking_metrics,
    compute_statistical_summary,
)


class TestBenchmarkMetrics(unittest.TestCase):
    def test_01_statistical_summary(self):
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = compute_statistical_summary(vals)
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["mean"], 30.0)
        self.assertEqual(stats["p50"], 30.0)
        self.assertEqual(stats["min"], 10.0)
        self.assertEqual(stats["max"], 50.0)
        self.assertAlmostEqual(stats["std_dev"], 15.81, places=1)
        self.assertLess(stats["ci95_lower"], stats["mean"])
        self.assertGreater(stats["ci95_upper"], stats["mean"])

    def test_02_classification_metrics(self):
        gold = ["OCR", "OCR", "Embedding", "Classification"]
        pred = ["OCR", "Classification", "Embedding", "Classification"]
        metrics = compute_classification_metrics(gold, pred)
        self.assertEqual(metrics["accuracy"], 0.75)
        self.assertEqual(metrics["total_samples"], 4)
        self.assertIn("OCR", metrics["per_class"])
        self.assertEqual(metrics["per_class"]["OCR"]["tp"], 1)
        self.assertEqual(metrics["per_class"]["OCR"]["fn"], 1)

    def test_03_retrieval_ranking_metrics(self):
        retrieved = [
            ["doc_A", "doc_B", "doc_C"],
            ["doc_X", "doc_Y", "doc_Z"],
        ]
        relevant = [
            {"doc_B"},
            {"doc_X"},
        ]
        # Query 1: doc_B found at rank 2 (RR = 0.5)
        # Query 2: doc_X found at rank 1 (RR = 1.0)
        # MRR = (0.5 + 1.0) / 2 = 0.75
        metrics = compute_retrieval_ranking_metrics(retrieved, relevant, k_values=(1, 3))
        self.assertEqual(metrics["mrr"], 0.75)
        self.assertEqual(metrics["recall@1"], 0.50)
        self.assertEqual(metrics["recall@3"], 1.0)

        # Test duplicate passages from the same document: Recall must NEVER exceed 1.0
        retrieved_with_duplicates = [
            ["doc_A", "doc_A", "doc_A", "doc_B"],
        ]
        relevant_single = [{"doc_A"}]
        dup_metrics = compute_retrieval_ranking_metrics(retrieved_with_duplicates, relevant_single, k_values=(1, 3))
        self.assertEqual(dup_metrics["recall@3"], 1.0)
        self.assertEqual(dup_metrics["precision@3"], round(1.0 / 3.0, 4))
        self.assertLessEqual(dup_metrics["recall@3"], 1.0)

    def test_04_qa_token_f1_and_em(self):
        em, f1 = compute_qa_token_f1_and_em("The cat sat on the mat.", "the cat sat on the mat")
        self.assertEqual(em, 1.0)
        self.assertEqual(f1, 1.0)

        em2, f12 = compute_qa_token_f1_and_em("The cat sat on the mat.", "The dog sat on the rug.")
        self.assertEqual(em2, 0.0)
        self.assertGreater(f12, 0.0)
        self.assertLess(f12, 1.0)

    def test_05_citation_metrics(self):
        extracted = [{"doc_id": "doc1", "page_number": 1, "block_id": 2}]
        expected = [{"doc_id": "doc1", "page_number": 1, "block_id": 2}]
        stats = compute_citation_metrics(extracted, expected)
        self.assertEqual(stats["citation_precision"], 1.0)
        self.assertEqual(stats["citation_completeness"], 1.0)

        # Mismatched citation
        mismatched = [{"doc_id": "doc2", "page_number": 5, "block_id": 9}]
        stats2 = compute_citation_metrics(mismatched, expected)
        self.assertEqual(stats2["citation_precision"], 0.0)
        self.assertEqual(stats2["citation_completeness"], 0.0)


if __name__ == "__main__":
    unittest.main()
