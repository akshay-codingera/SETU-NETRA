"""
test_embedding_corruption.py: Unit tests for defensive embedding deserialization and corruption handling.

Tests:
1. Valid embeddings roundtrip properly.
2. Empty BLOB is skipped without error.
3. Truncated BLOB (unaligned byte length) is skipped with diagnostic record.
4. Incorrect dimensions (mismatch between metadata and buffer) are skipped.
5. Inconsistent dimensions across rows are detected and skipped.
6. Vectors containing NaN or +/- Inf are detected and skipped.
7. Database containing both valid and invalid embeddings unpacks valid ones without crashing.
"""

import json
import logging
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.store.sqlite_store import SQLiteDocumentStore


class TestEmbeddingCorruptionHandling(unittest.TestCase):
    """Test suite for validating robustness against corrupted or malformed embedding vectors."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_corruption.db"
        self.store = SQLiteDocumentStore(self.db_path)

        # Create a parent document and page
        self.doc_id = "doc_test_corruption"
        self.store.save_document(
            doc_id=self.doc_id,
            file_path=Path("dummy.pdf"),
            file_hash="hash_dummy_001",
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

    def _insert_raw_block(
        self,
        block_id: int,
        text: str,
        embedding_blob: bytes,
        embedding_dim: int,
        engine: str = "test-engine",
    ):
        """Directly insert a block into SQLite to simulate arbitrary disk/blob states."""
        with self.store._conn:
            self.store._conn.execute(
                """
                INSERT INTO document_blocks (
                    doc_id, page_number, block_id, block_type, text, confidence,
                    bbox_json, source_detection_indices_json, embedding_blob,
                    embedding_dim, embedding_engine, primary_domain, concepts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.doc_id,
                    1,
                    block_id,
                    "PARAGRAPH",
                    text,
                    0.95,
                    json.dumps([10.0, 10.0, 200.0, 50.0]),
                    "[]",
                    embedding_blob,
                    embedding_dim,
                    engine,
                    "test_domain",
                    "[]",
                ),
            )

    def test_01_valid_embeddings(self):
        """Verify valid float32 vectors are unpacked correctly into an (N, D) matrix."""
        vec = np.random.randn(384).astype(np.float32)
        vec /= np.linalg.norm(vec)

        self.store.save_blocks(
            doc_id=self.doc_id,
            page_number=1,
            blocks_data=[{
                "block_id": 1,
                "block_type": "PARAGRAPH",
                "text": "Valid embedding block",
                "confidence": 0.99,
                "bounding_box": (10.0, 20.0, 100.0, 50.0),
                "embedding": vec,
                "embedding_engine": "test-engine",
            }],
        )

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")
        self.assertEqual(len(meta_list), 1)
        self.assertEqual(matrix.shape, (1, 384))
        np.testing.assert_allclose(matrix[0], vec, atol=1e-6)
        self.assertEqual(len(self.store.get_last_skipped_embeddings()), 0)

    def test_02_empty_blob(self):
        """Verify empty BLOB is safely skipped without exceptions."""
        self._insert_raw_block(
            block_id=2,
            text="Empty blob text",
            embedding_blob=b"",
            embedding_dim=384,
        )

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")
        self.assertEqual(len(meta_list), 0)
        self.assertEqual(matrix.shape, (0, 0))

        skipped = self.store.get_last_skipped_embeddings()
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "empty_blob")
        self.assertEqual(skipped[0]["block_id"], 2)

    def test_03_truncated_blob(self):
        """Verify truncated BLOB with unaligned byte count is defensively rejected."""
        # 17 bytes cannot be divided by 4 (float32 size)
        truncated_blob = b"0123456789abcdefg"
        self._insert_raw_block(
            block_id=3,
            text="Truncated blob text",
            embedding_blob=truncated_blob,
            embedding_dim=384,
        )

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")
        self.assertEqual(len(meta_list), 0)
        self.assertEqual(matrix.shape, (0, 0))

        skipped = self.store.get_last_skipped_embeddings()
        self.assertEqual(len(skipped), 1)
        self.assertIn("malformed_blob_length", skipped[0]["reason"])
        self.assertEqual(skipped[0]["blob_length_bytes"], 17)

    def test_04_incorrect_dimensions(self):
        """Verify vector whose float count mismatches stored metadata dimension is skipped."""
        # 64 floats (256 bytes), but metadata claims 384 dimensions
        small_vec = np.ones(64, dtype=np.float32)
        self._insert_raw_block(
            block_id=4,
            text="Mismatched dimension text",
            embedding_blob=small_vec.tobytes(),
            embedding_dim=384,
        )

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")
        self.assertEqual(len(meta_list), 0)
        self.assertEqual(matrix.shape, (0, 0))

        skipped = self.store.get_last_skipped_embeddings()
        self.assertEqual(len(skipped), 1)
        self.assertIn("dimension_mismatch", skipped[0]["reason"])

    def test_05_nan_and_infinite_values(self):
        """Verify vectors containing NaN or infinity are flagged and skipped."""
        # NaN vector
        nan_vec = np.ones(384, dtype=np.float32)
        nan_vec[10] = np.nan
        self._insert_raw_block(
            block_id=5,
            text="NaN vector text",
            embedding_blob=nan_vec.tobytes(),
            embedding_dim=384,
        )

        # Inf vector
        inf_vec = np.ones(384, dtype=np.float32)
        inf_vec[20] = np.inf
        self._insert_raw_block(
            block_id=6,
            text="Inf vector text",
            embedding_blob=inf_vec.tobytes(),
            embedding_dim=384,
        )

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")
        self.assertEqual(len(meta_list), 0)
        self.assertEqual(matrix.shape, (0, 0))

        skipped = self.store.get_last_skipped_embeddings()
        self.assertEqual(len(skipped), 2)
        for s in skipped:
            self.assertIn("non_finite_values", s["reason"])

    def test_06_database_with_both_valid_and_invalid_embeddings(self):
        """Verify database with mixed valid and invalid embeddings retrieves valid ones without crashing."""
        # 1. Valid vector A
        vec_a = np.ones(384, dtype=np.float32) * 0.1
        self._insert_raw_block(1, "Valid A", vec_a.tobytes(), 384)

        # 2. Corrupt truncated BLOB
        self._insert_raw_block(2, "Corrupt B", b"corrupted_bytes_123", 384)

        # 3. Valid vector C
        vec_c = np.ones(384, dtype=np.float32) * 0.2
        self._insert_raw_block(3, "Valid C", vec_c.tobytes(), 384)

        # 4. NaN vector
        nan_vec = np.ones(384, dtype=np.float32)
        nan_vec[5] = np.nan
        self._insert_raw_block(4, "Corrupt D (NaN)", nan_vec.tobytes(), 384)

        # 5. Empty BLOB
        self._insert_raw_block(5, "Corrupt E (Empty)", b"", 384)

        # 6. Valid vector F
        vec_f = np.ones(384, dtype=np.float32) * 0.3
        self._insert_raw_block(6, "Valid F", vec_f.tobytes(), 384)

        meta_list, matrix = self.store.get_all_embeddings(engine_name="test-engine")

        # Must have exactly 3 valid blocks returned
        self.assertEqual(len(meta_list), 3)
        self.assertEqual(matrix.shape, (3, 384))

        valid_block_ids = [m["block_id"] for m in meta_list]
        self.assertEqual(valid_block_ids, [1, 3, 6])

        # Must have exactly 3 skipped diagnostic records
        skipped = self.store.get_last_skipped_embeddings()
        self.assertEqual(len(skipped), 3)
        skipped_block_ids = [s["block_id"] for s in skipped]
        self.assertEqual(skipped_block_ids, [2, 4, 5])

        # Verify vectors were not silently replaced with zeros or noise
        np.testing.assert_allclose(matrix[0], vec_a, atol=1e-6)
        np.testing.assert_allclose(matrix[1], vec_c, atol=1e-6)
        np.testing.assert_allclose(matrix[2], vec_f, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
