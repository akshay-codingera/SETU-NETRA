"""
test_hybrid_score_robustness.py: Comprehensive test suite for dense score robustness,
negative cosine regularization, and hybrid scoring combinations.

Tests:
1. Strong dense, weak lexical (semantic match without keyword overlap).
2. Weak dense, strong lexical (keyword match without strong semantic affinity).
3. Negative dense, strong lexical (exact keywords present, but vector cosine is negative).
4. Both scores weak (irrelevant block correctly rejected below threshold).
5. Identical passages (query matches passage verbatim).
6. Empty or whitespace query (returns empty list immediately).
7. Independent testability of dense-only (alpha=1.0) and lexical-only (alpha=0.0).
8. Mathematical validation of rectify_dense_score and compute_hybrid_score.
"""

import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import RetrievedPassage
from setu_netra.retrieval.document_retriever import (
    DocumentRetriever,
    compute_hybrid_score,
    compute_lexical_similarity,
    rectify_dense_score,
    tokenize_text,
)
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class DummyControlledEmbeddingEngine(BaseEmbeddingEngine):
    """Deterministic embedding engine for controlled scoring tests."""

    def __init__(self, vector_map=None, default_dim=4):
        self.vector_map = vector_map or {}
        self.default_dim = default_dim

    @property
    def engine_name(self) -> str:
        return "controlled-test-engine"

    @property
    def dimension(self) -> int:
        return self.default_dim

    def is_available(self) -> bool:
        return True

    def embed_texts(self, texts):
        results = []
        for t in texts:
            if t in self.vector_map:
                v = np.array(self.vector_map[t], dtype=np.float32)
            else:
                v = np.ones(self.default_dim, dtype=np.float32)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            results.append(v)
        return np.vstack(results)


class TestHybridScoreRobustness(unittest.TestCase):
    """Test suite validating hybrid scoring and dense score regularization."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_hybrid.db"
        self.store = SQLiteDocumentStore(self.db_path)

        self.doc_id = "doc_scoring_eval"
        self.store.save_document(
            doc_id=self.doc_id,
            file_path=Path("scoring.pdf"),
            file_hash="hash_scoring_123",
            file_type="PDF",
            page_count=1,
        )
        self.store.save_page(
            page_id=f"{self.doc_id}_p1",
            doc_id=self.doc_id,
            page_number=1,
            width=800,
            height=1000,
        )

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_01_rectify_dense_score_mathematical_properties(self):
        """Verify rectify_dense_score clips negative values to 0.0 and preserves positive values in [0, 1]."""
        # Negative values clipped to 0.0
        self.assertEqual(rectify_dense_score(-0.75), 0.0)
        self.assertEqual(rectify_dense_score(-0.001), 0.0)
        self.assertEqual(rectify_dense_score(-1.0), 0.0)

        # Zero and positive values preserved exactly
        self.assertEqual(rectify_dense_score(0.0), 0.0)
        self.assertAlmostEqual(rectify_dense_score(0.42), 0.42, places=6)
        self.assertAlmostEqual(rectify_dense_score(0.85), 0.85, places=6)
        self.assertEqual(rectify_dense_score(1.0), 1.0)

        # Extreme positive overflow clamped to 1.0
        self.assertEqual(rectify_dense_score(1.05), 1.0)

        # Unnormalized mode returns raw float
        self.assertEqual(rectify_dense_score(-0.45, method="none"), -0.45)

    def test_02_strong_dense_weak_lexical(self):
        """Verify semantic paraphrases without shared keywords achieve high hybrid scores."""
        # Query: [1, 0, 0, 0], Target: [1, 0, 0, 0] -> cosine = 1.0
        # Zero word overlap
        engine = DummyControlledEmbeddingEngine(
            vector_map={
                "volatile main storage": [1.0, 0.0, 0.0, 0.0],
                "random access memory hardware architecture": [1.0, 0.0, 0.0, 0.0],
            }
        )
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 1,
                "text": "random access memory hardware architecture",
                "embedding": [1.0, 0.0, 0.0, 0.0],
                "embedding_engine": engine.engine_name,
                "confidence": 0.95,
                "bounding_box": (10, 10, 100, 40),
            }],
        )

        retriever = DocumentRetriever(self.store, engine, default_alpha=0.70)
        results = retriever.retrieve("volatile main storage", top_k=1, threshold=0.20)

        self.assertEqual(len(results), 1)
        passage = results[0]
        self.assertAlmostEqual(passage.metadata["raw_dense_score"], 1.0, places=3)
        self.assertEqual(passage.metadata["lexical_score"], 0.0)
        # Hybrid = 0.70 * 1.0 + 0.30 * 0.0 = 0.70
        self.assertAlmostEqual(passage.similarity_score, 0.70, places=3)

    def test_03_weak_dense_strong_lexical(self):
        """Verify exact keyword matches with neutral/low semantic affinity are successfully retrieved."""
        # Query: [1, 0, 0, 0], Target: [0, 1, 0, 0] -> cosine = 0.0
        # High token overlap: "unique identifier code x98"
        engine = DummyControlledEmbeddingEngine(
            vector_map={
                "unique identifier code x98": [1.0, 0.0, 0.0, 0.0],
                "the block has unique identifier code x98": [0.0, 1.0, 0.0, 0.0],
            }
        )
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 2,
                "text": "the block has unique identifier code x98",
                "embedding": [0.0, 1.0, 0.0, 0.0],
                "embedding_engine": engine.engine_name,
                "confidence": 0.95,
                "bounding_box": (10, 50, 100, 90),
            }],
        )

        retriever = DocumentRetriever(self.store, engine, default_alpha=0.70)
        results = retriever.retrieve("unique identifier code x98", top_k=1, threshold=0.15)

        self.assertEqual(len(results), 1)
        passage = results[0]
        self.assertAlmostEqual(passage.metadata["raw_dense_score"], 0.0, places=3)
        self.assertGreater(passage.metadata["lexical_score"], 0.70)
        # Hybrid = 0.70 * 0.0 + 0.30 * lexical_sim > 0.15
        self.assertGreaterEqual(passage.similarity_score, 0.15)

    def test_04_negative_dense_strong_lexical_not_penalized(self):
        """CRITICAL: Verify negative cosine similarity does NOT drag down a strong lexical match below threshold."""
        # Query: [1, 0, 0, 0], Target: [-1, 0, 0, 0] -> raw cosine = -1.0
        # But text has strong keyword overlap: "hyperparameter tuning configuration batch_size"
        query_text = "hyperparameter tuning configuration batch_size"
        block_text = "advanced hyperparameter tuning configuration batch_size in model"

        engine = DummyControlledEmbeddingEngine(
            vector_map={
                query_text: [1.0, 0.0, 0.0, 0.0],
                block_text: [-1.0, 0.0, 0.0, 0.0],
            }
        )
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 3,
                "text": block_text,
                "embedding": [-1.0, 0.0, 0.0, 0.0],
                "embedding_engine": engine.engine_name,
                "confidence": 0.95,
                "bounding_box": (10, 100, 100, 140),
            }],
        )

        # 1. With rectification (Default / Robust mode)
        retriever_robust = DocumentRetriever(self.store, engine, default_alpha=0.70)
        results_robust = retriever_robust.retrieve(query_text, top_k=1, threshold=0.15, normalize_dense=True)

        self.assertEqual(len(results_robust), 1, "Rectified scoring should retrieve strong lexical match!")
        res = results_robust[0]
        self.assertEqual(res.metadata["raw_dense_score"], -1.0)
        self.assertEqual(res.metadata["normalized_dense_score"], 0.0)
        self.assertGreater(res.metadata["lexical_score"], 0.70)
        # Hybrid = 0.70 * 0.0 + 0.30 * 0.77 = 0.231 >= 0.15
        self.assertGreaterEqual(res.similarity_score, 0.15)

        # 2. Without rectification (Unnormalized mode):
        # Raw hybrid = 0.70 * (-1.0) + 0.30 * 0.77 = -0.70 + 0.231 = -0.469 < 0.15 -> DROPPED!
        results_unnormalized = retriever_robust.retrieve(query_text, top_k=1, threshold=0.15, normalize_dense=False)
        self.assertEqual(len(results_unnormalized), 0, "Unnormalized scoring should fail due to negative drag!")

    def test_05_both_scores_weak_rejected(self):
        """Verify irrelevant passages with both weak dense and weak lexical scores are filtered out."""
        # Query: [1, 0, 0, 0], Target: [0, 1, 0, 0] -> cosine = 0.0
        # No common keywords
        engine = DummyControlledEmbeddingEngine(
            vector_map={
                "quantum mechanics wave equation": [1.0, 0.0, 0.0, 0.0],
                "botany photosynthesis chlorophyll": [0.0, 1.0, 0.0, 0.0],
            }
        )
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 4,
                "text": "botany photosynthesis chlorophyll",
                "embedding": [0.0, 1.0, 0.0, 0.0],
                "embedding_engine": engine.engine_name,
                "confidence": 0.95,
                "bounding_box": (10, 150, 100, 190),
            }],
        )

        retriever = DocumentRetriever(self.store, engine, default_alpha=0.70)
        results = retriever.retrieve("quantum mechanics wave equation", top_k=1, threshold=0.20)
        self.assertEqual(len(results), 0)

    def test_06_identical_passages(self):
        """Verify identical query and passage achieves near 1.0 similarity score."""
        text = "central processing unit executes machine instructions"
        engine = DummyControlledEmbeddingEngine(
            vector_map={text: [0.5, 0.5, 0.5, 0.5]}
        )
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 5,
                "text": text,
                "embedding": [0.5, 0.5, 0.5, 0.5],
                "embedding_engine": engine.engine_name,
                "confidence": 0.99,
                "bounding_box": (10, 200, 100, 240),
            }],
        )

        retriever = DocumentRetriever(self.store, engine, default_alpha=0.70)
        results = retriever.retrieve(text, top_k=1, threshold=0.80)

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].similarity_score, 1.0, places=3)
        self.assertAlmostEqual(results[0].metadata["lexical_score"], 1.0, places=3)
        self.assertAlmostEqual(results[0].metadata["normalized_dense_score"], 1.0, places=3)

    def test_07_empty_and_whitespace_query(self):
        """Verify empty, None-like, or whitespace-only queries return empty list immediately."""
        engine = DummyControlledEmbeddingEngine()
        retriever = DocumentRetriever(self.store, engine)

        self.assertEqual(retriever.retrieve(""), [])
        self.assertEqual(retriever.retrieve("   "), [])
        self.assertEqual(retriever.retrieve("\n\t  \n"), [])

    def test_08_alpha_modes_independent_testability(self):
        """Verify pure dense (alpha=1.0) and pure lexical (alpha=0.0) operate independently."""
        q = "test query"
        t = "test passage"
        engine = DummyControlledEmbeddingEngine(vector_map={q: [1, 0, 0, 0], t: [0.6, 0.8, 0, 0]})
        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 6,
                "text": t,
                "embedding": [0.6, 0.8, 0, 0],
                "embedding_engine": engine.engine_name,
                "confidence": 0.95,
                "bounding_box": (10, 250, 100, 290),
            }],
        )

        retriever = DocumentRetriever(self.store, engine)

        # Pure dense: similarity_score must strictly equal normalized_dense_score
        dense_results = retriever.retrieve(q, alpha=1.0, threshold=0.1)
        self.assertEqual(len(dense_results), 1)
        self.assertEqual(dense_results[0].retrieval_method, "dense")
        self.assertEqual(dense_results[0].similarity_score, dense_results[0].metadata["normalized_dense_score"])

        # Pure lexical: similarity_score must strictly equal lexical_score
        lex_results = retriever.retrieve(q, alpha=0.0, threshold=0.1)
        self.assertEqual(len(lex_results), 1)
        self.assertEqual(lex_results[0].retrieval_method, "lexical")
        self.assertEqual(lex_results[0].similarity_score, lex_results[0].metadata["lexical_score"])


if __name__ == "__main__":
    unittest.main()
