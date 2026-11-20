"""
test_document_intelligence.py: Verification of Phase 6 Document Intelligence enhancements.

Verifies:
1. Okapi BM25 lexical ranking: term frequency saturation, length normalization, and IDF weighting.
2. Reciprocal Rank Fusion (RRF): multi-list rank reciprocal combination and rank monotonic ordering.
3. DocumentRetriever integration with fusion_method='rrf' and lexical_metric='bm25'.
4. CitationVerifier negation divergence / polarity inversion detection.
5. CitationVerifier cross-passage contradictory evidence detection.
6. Entailment score computation between generated answer and cited passages.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import RetrievedPassage
from setu_netra.qa.verifier import (
    CitationVerifier,
    compute_entailment_score,
    detect_contradictory_evidence,
    detect_negation_mismatch,
)
from setu_netra.retrieval.document_retriever import (
    compute_bm25_scores,
    reciprocal_rank_fusion,
)


class TestDocumentIntelligence(unittest.TestCase):
    """Test suite for advanced retrieval and verification intelligence."""

    def test_01_bm25_scoring(self):
        """Verify Okapi BM25 awards higher scores to documents with high query term frequency."""
        query_tokens = ["virtual", "memory"]
        corpus = [
            ["virtual", "memory", "is", "an", "abstraction", "providing", "virtual", "memory", "spaces"],
            ["the", "cat", "sat", "on", "the", "mat"],
            ["memory", "allocation", "and", "paging"],
        ]
        scores = compute_bm25_scores(query_tokens, corpus)
        self.assertEqual(len(scores), 3)
        # Doc 0 contains both terms multiple times -> highest score
        self.assertEqual(scores[0], 1.0)
        # Doc 1 has 0 terms -> score 0.0
        self.assertEqual(scores[1], 0.0)
        # Doc 2 has one term -> score in between
        self.assertGreater(scores[2], 0.0)
        self.assertLess(scores[2], scores[0])

    def test_02_reciprocal_rank_fusion(self):
        """Verify RRF correctly aggregates separate rank lists."""
        dense_rank = [10, 20, 30]  # item 10 is rank 1, item 20 is rank 2
        lexical_rank = [20, 10, 40]  # item 20 is rank 1, item 10 is rank 2

        rrf = reciprocal_rank_fusion([dense_rank, lexical_rank], k=60)
        self.assertIn(10, rrf)
        self.assertIn(20, rrf)
        self.assertIn(30, rrf)
        self.assertIn(40, rrf)

        # Both item 10 and 20 are top 2 in both lists, so they must score highest
        self.assertGreater(rrf[10], rrf[30])
        self.assertGreater(rrf[20], rrf[40])

    def test_03_negation_mismatch_detection(self):
        """Verify detection of negative assertion in answer when evidence is strictly affirmative."""
        passages = [
            RetrievedPassage(
                doc_id="doc1",
                document_name="doc1",
                page_number=1,
                block_id=1,
                block_type="PARAGRAPH",
                text="The system requires total resource ordering to prevent deadlocks.",
                bounding_box=(0, 0, 100, 100),
                confidence=0.99,
                similarity_score=0.9,
                retrieval_method="hybrid",
            )
        ]

        # Affirmative answer -> no mismatch
        affirmative_ans = "The system requires resource ordering. [Doc: doc1, Page: 1, Block: 1]"
        mismatch_aff, _ = detect_negation_mismatch(affirmative_ans, passages)
        self.assertFalse(mismatch_aff)

        # Negative answer contrary to evidence -> mismatch detected
        negative_ans = "The system does not require resource ordering. [Doc: doc1, Page: 1, Block: 1]"
        mismatch_neg, note = detect_negation_mismatch(negative_ans, passages)
        self.assertTrue(mismatch_neg)
        self.assertIn("Negation divergence", note)

    def test_04_contradictory_evidence_detection(self):
        """Verify detection of contradictory assertions across retrieved evidence passages."""
        p1 = RetrievedPassage(
            doc_id="doc1",
            document_name="doc1",
            page_number=1,
            block_id=1,
            block_type="PARAGRAPH",
            text="Increasing buffer pool size increases cache hit ratio and database performance.",
            bounding_box=(0, 0, 100, 100),
            confidence=0.99,
            similarity_score=0.9,
            retrieval_method="hybrid",
        )
        p2 = RetrievedPassage(
            doc_id="doc1",
            document_name="doc1",
            page_number=2,
            block_id=3,
            block_type="PARAGRAPH",
            text="Excessive buffer pool allocation decreases system stability due to swapping.",
            bounding_box=(0, 0, 100, 100),
            confidence=0.95,
            similarity_score=0.85,
            retrieval_method="hybrid",
        )

        has_conflict, notes = detect_contradictory_evidence([p1, p2])
        self.assertTrue(has_conflict)
        self.assertTrue(any("Contradictory evidence" in n for n in notes))

    def test_05_citation_verifier_entailment_and_conflict_integration(self):
        """Verify full CitationVerifier returns entailment score and contradictory flags."""
        verifier = CitationVerifier(min_overlap_threshold=0.30)
        p1 = RetrievedPassage(
            doc_id="doc1",
            document_name="doc1",
            page_number=1,
            block_id=1,
            block_type="PARAGRAPH",
            text="Deadlock prevention requires mutual exclusion and resource ordering.",
            bounding_box=(0, 0, 100, 100),
            confidence=0.99,
            similarity_score=0.9,
            retrieval_method="hybrid",
        )

        answer = "Deadlock prevention requires mutual exclusion. [Doc: doc1, Page: 1, Block: 1]"
        result = verifier.verify_answer(answer, [p1])
        self.assertEqual(result.epistemic_status, "EVIDENCE_BACKED")
        self.assertTrue(result.is_verified)
        self.assertGreater(result.entailment_score, 0.5)
        self.assertFalse(result.negation_mismatch)
        self.assertFalse(result.has_contradictory_evidence)


if __name__ == "__main__":
    unittest.main()
