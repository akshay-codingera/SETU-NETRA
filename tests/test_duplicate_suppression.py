"""
test_duplicate_suppression.py: Unit and integration tests for duplicate passage suppression
and repeated header filtering in DocumentRetriever.

Tests:
1. Exact duplicate blocks within the same document are suppressed.
2. Near-duplicate blocks with minor phrasing/spelling variations are suppressed.
3. Repeated page headers across different pages are suppressed.
4. Semantically distinct passages with overlapping words are NOT suppressed.
5. Identical text appearing across different documents is suppressed from top-K.
6. Configurable suppression threshold and enable/disable flag.
7. Verification of suppressed duplicate diagnostic metadata.
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
    compute_text_similarity,
)
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class SimpleDeterministicEmbeddingEngine(BaseEmbeddingEngine):
    """Deterministic embedding engine based on word hashing for duplicate tests."""

    def __init__(self, dimension: int = 16):
        self._dim = dimension

    @property
    def engine_name(self) -> str:
        return "deterministic-dup-engine"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def embed_texts(self, texts):
        matrix = []
        for text in texts:
            vec = np.zeros(self._dim, dtype=np.float32)
            for word in text.lower().split():
                idx = hash(word) % self._dim
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            matrix.append(vec)
        return np.vstack(matrix)


class TestDuplicateSuppression(unittest.TestCase):
    """Test suite validating duplicate passage suppression and repeated header elimination."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dup.db"
        self.store = SQLiteDocumentStore(self.db_path)
        self.engine = SimpleDeterministicEmbeddingEngine()

        # Document 1: 3-page exam paper with repeated headers
        self.doc1_id = "exam_paper_2024"
        self.store.save_document(
            doc_id=self.doc1_id,
            file_path=Path("exam2024.pdf"),
            file_hash="hash_exam_2024",
            file_type="PDF",
            page_count=3,
        )
        for p in range(1, 4):
            self.store.save_page(
                page_id=f"{self.doc1_id}_p{p}",
                doc_id=self.doc1_id,
                page_number=p,
                width=800,
                height=1100,
            )

        # Document 2: Different document containing an identical disclaimer
        self.doc2_id = "syllabus_2024"
        self.store.save_document(
            doc_id=self.doc2_id,
            file_path=Path("syllabus.pdf"),
            file_hash="hash_syllabus_2024",
            file_type="PDF",
            page_count=1,
        )
        self.store.save_page(
            page_id=f"{self.doc2_id}_p1",
            doc_id=self.doc2_id,
            page_number=1,
            width=800,
            height=1100,
        )

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_01_text_similarity_metric(self):
        """Verify compute_text_similarity accurately identifies duplicates and distinguishes separate questions."""
        # Exact identical text
        self.assertEqual(compute_text_similarity("Hello World", "hello world"), 1.0)
        self.assertEqual(compute_text_similarity("  Extra   spaces  ", "extra spaces"), 1.0)

        # Repeated headers across pages
        h1 = "CENTRAL BOARD OF SECONDARY EDUCATION ANNUAL EXAMINATION 2024 PAGE 1"
        h2 = "CENTRAL BOARD OF SECONDARY EDUCATION ANNUAL EXAMINATION 2024 PAGE 2"
        self.assertGreater(compute_text_similarity(h1, h2), 0.90)

        # Minor punctuation or typo
        t1 = "All answers must be written in blue or black ballpoint pen."
        t2 = "All answers must be written in blue or black ball-point pen!"
        self.assertGreater(compute_text_similarity(t1, t2), 0.85)

        # Semantically distinct questions sharing common words
        q1 = "What is the time complexity of bubble sort in worst case?"
        q2 = "What is the space complexity of quick sort in average case?"
        self.assertLess(compute_text_similarity(q1, q2), 0.75)

        # Completely different texts
        self.assertLess(compute_text_similarity("Quantum physics", "Plant photosynthesis"), 0.20)

    def test_02_exact_duplicate_blocks(self):
        """Verify exact duplicate blocks within a document are deduplicated in top-K."""
        dup_text = "Important Instruction: Candidates must verify that question booklet contains 50 questions."

        # Insert block on page 1 and identical block on page 2
        vec = self.engine.embed_texts([dup_text])[0]
        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=1,
            blocks_data=[{
                "block_id": 1,
                "text": dup_text,
                "embedding": vec,
                "embedding_engine": self.engine.engine_name,
                "confidence": 0.98,
                "bounding_box": (10, 10, 500, 40),
            }],
        )
        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=2,
            blocks_data=[{
                "block_id": 1,
                "text": dup_text,
                "embedding": vec,
                "embedding_engine": self.engine.engine_name,
                "confidence": 0.98,
                "bounding_box": (10, 10, 500, 40),
            }],
        )

        retriever = DocumentRetriever(self.store, self.engine, duplicate_threshold=0.85)

        # With duplicate suppression enabled: Only 1 passage returned
        results = retriever.retrieve("Candidates must verify question booklet", top_k=5, suppress_duplicates=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].text, dup_text)
        self.assertEqual(results[0].page_number, 1)

        # Verify diagnostic suppression log
        suppressed = retriever.last_suppressed_duplicates
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0]["suppressed_page"], 2)
        self.assertEqual(suppressed[0]["matched_page"], 1)
        self.assertEqual(suppressed[0]["similarity"], 1.0)

        # Without duplicate suppression (flag disabled): Both passages returned
        raw_results = retriever.retrieve("Candidates must verify question booklet", top_k=5, suppress_duplicates=False)
        self.assertEqual(len(raw_results), 2)

    def test_03_near_duplicate_blocks(self):
        """Verify near-duplicate passages with minor typographical variations are suppressed."""
        text_orig = "The primary component of volatile memory is dynamic random-access memory (DRAM)."
        text_typo = "The primary component of volatile memory is dynamic random access memory (DRAM)."

        vec_orig = self.engine.embed_texts([text_orig])[0]
        vec_typo = self.engine.embed_texts([text_typo])[0]

        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=1,
            blocks_data=[
                {
                    "block_id": 1,
                    "text": text_orig,
                    "embedding": vec_orig,
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.99,
                    "bounding_box": (10, 10, 500, 40),
                },
                {
                    "block_id": 2,
                    "text": text_typo,
                    "embedding": vec_typo,
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.95,
                    "bounding_box": (10, 50, 500, 80),
                },
            ],
        )

        retriever = DocumentRetriever(self.store, self.engine)
        results = retriever.retrieve("volatile memory DRAM", top_k=3, suppress_duplicates=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(retriever.last_suppressed_duplicates), 1)
        self.assertGreaterEqual(retriever.last_suppressed_duplicates[0]["similarity"], 0.90)

    def test_04_repeated_page_headers(self):
        """Verify repeated headers across 3 pages of an exam paper do not saturate top-K."""
        h1 = "EXAMINATION 2024 - COMPUTER SCIENCE - PAGE 1"
        h2 = "EXAMINATION 2024 - COMPUTER SCIENCE - PAGE 2"
        h3 = "EXAMINATION 2024 - COMPUTER SCIENCE - PAGE 3"
        q1 = "Question 1: Define time complexity and give Big-O notation."

        for p_num, h_text in [(1, h1), (2, h2), (3, h3)]:
            blocks = [
                {
                    "block_id": 1,
                    "block_type": "HEADING",
                    "text": h_text,
                    "embedding": self.engine.embed_texts([h_text])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.99,
                    "bounding_box": (10, 10, 700, 30),
                }
            ]
            if p_num == 1:
                blocks.append({
                    "block_id": 2,
                    "block_type": "QUESTION",
                    "text": q1,
                    "embedding": self.engine.embed_texts([q1])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.97,
                    "bounding_box": (10, 40, 700, 80),
                })
            self.store.save_blocks(doc_id=self.doc1_id, page_number=p_num, blocks_data=blocks)

        retriever = DocumentRetriever(self.store, self.engine)

        # Query matching the header
        results = retriever.retrieve("EXAMINATION 2024 COMPUTER SCIENCE", top_k=3, suppress_duplicates=True)

        # Exactly 1 header should be returned, plus the non-header block if relevant
        header_results = [r for r in results if "EXAMINATION 2024" in r.text]
        self.assertEqual(len(header_results), 1, "Only 1 header should be returned instead of all 3 pages!")
        self.assertEqual(len(retriever.last_suppressed_duplicates), 2)

    def test_05_similar_but_semantically_distinct_passages_not_suppressed(self):
        """CRITICAL: Distinct questions sharing vocabulary must NOT be suppressed."""
        q_bubble = "Question 1: What is the time complexity of bubble sort in the worst case scenario?"
        q_quick = "Question 2: What is the space complexity of quick sort in the average case scenario?"

        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=1,
            blocks_data=[
                {
                    "block_id": 1,
                    "text": q_bubble,
                    "embedding": self.engine.embed_texts([q_bubble])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.98,
                    "bounding_box": (10, 10, 600, 40),
                },
                {
                    "block_id": 2,
                    "text": q_quick,
                    "embedding": self.engine.embed_texts([q_quick])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.98,
                    "bounding_box": (10, 50, 600, 80),
                },
            ],
        )

        retriever = DocumentRetriever(self.store, self.engine)
        results = retriever.retrieve("What is complexity of sort", top_k=5, suppress_duplicates=True)

        self.assertEqual(len(results), 2, "Both distinct questions must be returned!")
        block_texts = [r.text for r in results]
        self.assertIn(q_bubble, block_texts)
        self.assertIn(q_quick, block_texts)
        self.assertEqual(len(retriever.last_suppressed_duplicates), 0)

    def test_06_identical_text_across_different_documents(self):
        """Verify identical text across different documents is deduplicated in unified retrieval."""
        disclaimer = "General Disclaimer: Unauthorized reproduction of this assessment paper is prohibited."

        # Insert disclaimer into Doc 1 and Doc 2
        vec = self.engine.embed_texts([disclaimer])[0]
        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=1,
            blocks_data=[{
                "block_id": 10,
                "text": disclaimer,
                "embedding": vec,
                "embedding_engine": self.engine.engine_name,
                "confidence": 0.99,
                "bounding_box": (10, 900, 600, 930),
            }],
        )
        self.store.save_blocks(
            doc_id=self.doc2_id,
            page_number=1,
            blocks_data=[{
                "block_id": 20,
                "text": disclaimer,
                "embedding": vec,
                "embedding_engine": self.engine.engine_name,
                "confidence": 0.99,
                "bounding_box": (10, 900, 600, 930),
            }],
        )

        retriever = DocumentRetriever(self.store, self.engine)
        results = retriever.retrieve("Unauthorized reproduction is prohibited", top_k=5, suppress_duplicates=True)

        self.assertEqual(len(results), 1, "Only one copy of the cross-document disclaimer should be returned!")
        suppressed = retriever.last_suppressed_duplicates
        self.assertEqual(len(suppressed), 1)
        self.assertNotEqual(suppressed[0]["suppressed_doc_id"], suppressed[0]["matched_doc_id"])

    def test_07_configurable_threshold(self):
        """Verify duplicate threshold can be customized or tightened/loosened."""
        t1 = "Option A: Binary search algorithm"
        t2 = "Option B: Linear search algorithm"
        # Token overlap: "option", "search", "algorithm" (3/5 tokens = 0.60)

        self.store.save_blocks(
            doc_id=self.doc1_id,
            page_number=1,
            blocks_data=[
                {
                    "block_id": 1,
                    "text": t1,
                    "embedding": self.engine.embed_texts([t1])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.95,
                    "bounding_box": (10, 10, 300, 30),
                },
                {
                    "block_id": 2,
                    "text": t2,
                    "embedding": self.engine.embed_texts([t2])[0],
                    "embedding_engine": self.engine.engine_name,
                    "confidence": 0.95,
                    "bounding_box": (10, 40, 300, 60),
                },
            ],
        )

        retriever = DocumentRetriever(self.store, self.engine)

        # Under default threshold (0.85): Both options accepted
        res_default = retriever.retrieve("search algorithm", top_k=5, duplicate_threshold=0.85)
        self.assertEqual(len(res_default), 2)

        # Under aggressive threshold (0.50): Second option suppressed as duplicate
        res_aggressive = retriever.retrieve("search algorithm", top_k=5, duplicate_threshold=0.50)
        self.assertEqual(len(res_aggressive), 1)


if __name__ == "__main__":
    unittest.main()
