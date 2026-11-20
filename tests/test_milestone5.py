"""
test_milestone5.py: Automated Acceptance Tests for Milestone 5.

Verifies:
1. Multi-Page PDF validation, decomposition, and page rendering.
2. Persistent SQLite document storage and state reusability across restarts.
3. Content deduplication via SHA-256 hashing.
4. Grounded hybrid semantic & lexical retrieval over multi-document corpora.
5. Strict provenance preservation (bounding box, page number, block ID).
6. Token-budgeted context prompt packaging with structured citation tags.
7. End-to-end multi-page document intelligence pipeline execution.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure src is on sys.path regardless of execution environment
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
from PIL import Image, ImageDraw

from setu_netra.context.synthesizer import EvidenceContextSynthesizer, estimate_token_count
from setu_netra.core.contracts import (
    RetrievedPassage,
    StoredDocument,
    SynthesizedContext,
    ValidationResult,
)
from setu_netra.ingestion.pdf_loader import (
    get_pdf_page_count,
    is_pdfium_available,
    load_pdf_pages,
)
from setu_netra.ingestion.validator import validate_document_file, validate_image_file
from setu_netra.ocr.mock_engine import MockOCREngine
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.retrieval.document_retriever import DocumentRetriever, tokenize_text
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore, compute_file_sha256


def create_synthetic_pdf(
    file_path: Path,
    page_texts: list[str],
    width: int = 500,
    height: int = 400,
) -> Path:
    """Helper to generate a multi-page PDF using PIL Image drawing."""
    images = []
    for idx, txt in enumerate(page_texts, start=1):
        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), f"PAGE {idx}: {txt}", fill="black")
        draw.rectangle([25, 25, width - 25, height - 25], outline="black", width=2)
        images.append(img)

    images[0].save(file_path, save_all=True, append_images=images[1:])
    return file_path


class TestMilestone5Acceptance(unittest.TestCase):
    """Concrete acceptance test suite for Milestone 5."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="setu_test_m5_"))
        self.db_path = self.temp_dir / "test_store.db"
        self.store = SQLiteDocumentStore(self.db_path)
        self.embedding_engine = OfflineSemanticEngine(dimension=512)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ==========================================================================
    # Acceptance Test 1: Multi-Page PDF Decomposition & Validation
    # ==========================================================================

    def test_01_pdf_validation_and_header_check(self):
        """Verify that validate_document_file accepts valid PDFs and rejects corrupt ones."""
        pdf_path = self.temp_dir / "sample.pdf"
        create_synthetic_pdf(pdf_path, ["First Page", "Second Page"])

        # 1. Valid PDF validation
        val_res = validate_document_file(pdf_path)
        self.assertTrue(val_res.is_valid, f"Validation failed: {val_res.error_message}")
        self.assertIsNone(val_res.error_message)

        # 2. Fake / Corrupted PDF validation (wrong magic bytes)
        fake_pdf = self.temp_dir / "corrupted.pdf"
        fake_pdf.write_text("THIS IS NOT A VALID PDF FILE HEADER", encoding="utf-8")
        val_fake = validate_document_file(fake_pdf)
        self.assertFalse(val_fake.is_valid)
        self.assertIn("Invalid PDF header", val_fake.error_message)

    def test_02_pdf_decomposition_and_page_rendering(self):
        """Verify that multi-page PDFs are decomposed into sequential PIL pages."""
        if not is_pdfium_available():
            self.skipTest("pypdfium2 not installed in this environment")

        pdf_path = self.temp_dir / "multipage_doc.pdf"
        page_texts = [
            "Introduction to Digital Signal Processing",
            "Discrete Fourier Transform and Convolution",
            "Filter Design and Computational Complexity",
        ]
        create_synthetic_pdf(pdf_path, page_texts, width=600, height=450)

        # Check fast page count
        page_count = get_pdf_page_count(pdf_path)
        self.assertEqual(page_count, 3)

        # Render all pages
        pages = load_pdf_pages(pdf_path, dpi=150)
        self.assertEqual(len(pages), 3)

        for expected_num, (page_num, pil_img, w, h) in enumerate(pages, start=1):
            self.assertEqual(page_num, expected_num)
            self.assertIsInstance(pil_img, Image.Image)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            self.assertEqual(pil_img.size, (w, h))

    # ==========================================================================
    # Acceptance Test 2: Persistent Storage & Reusability Across Restarts
    # ==========================================================================

    def test_03_persistent_storage_across_process_restarts(self):
        """Verify that documents, pages, blocks, and embeddings survive DB reconnect."""
        doc_id = "doc_test_persistent_001"
        file_path = self.temp_dir / "source_doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 test document content for hash calculation")
        file_hash = compute_file_sha256(file_path)

        # 1. Save document, page, and blocks in initial session
        doc = self.store.save_document(
            doc_id=doc_id,
            file_path=file_path,
            file_hash=file_hash,
            file_type="PDF",
            page_count=2,
            metadata={"department": "Computer Science"},
        )
        self.assertEqual(doc.doc_id, doc_id)

        self.store.save_page(
            page_id=f"{doc_id}_p1",
            doc_id=doc_id,
            page_number=1,
            width=1200,
            height=800,
        )

        test_vec = np.ones(512, dtype=np.float32) / np.sqrt(512.0)
        blocks = [
            {
                "block_id": 1,
                "block_type": "QUESTION",
                "text": "What is the time complexity of quicksort in the average case?",
                "confidence": 0.95,
                "bounding_box": (50.0, 100.0, 500.0, 150.0),
                "embedding": test_vec,
                "embedding_engine": self.embedding_engine.engine_name,
            },
            {
                "block_id": 2,
                "block_type": "OPTION",
                "text": "[A] O(N log N)",
                "confidence": 0.98,
                "bounding_box": (50.0, 160.0, 200.0, 190.0),
                "embedding": test_vec,
                "embedding_engine": self.embedding_engine.engine_name,
            },
        ]
        saved_count = self.store.save_blocks(doc_id=doc_id, page_number=1, blocks_data=blocks)
        self.assertEqual(saved_count, 2)

        # 2. Simulate process restart by closing connection and creating a new store instance
        self.store.close()
        restarted_store = SQLiteDocumentStore(self.db_path)

        # 3. Verify data integrity after restart
        restored_doc = restarted_store.get_document_by_id(doc_id)
        self.assertIsNotNone(restored_doc)
        self.assertEqual(restored_doc.file_name, "source_doc.pdf")
        self.assertEqual(restored_doc.file_hash, file_hash)
        self.assertEqual(restored_doc.page_count, 2)
        self.assertEqual(restored_doc.metadata.get("department"), "Computer Science")

        pages = restarted_store.get_pages(doc_id)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].width, 1200)

        restored_blocks = restarted_store.get_blocks(doc_id=doc_id, page_number=1)
        self.assertEqual(len(restored_blocks), 2)
        self.assertEqual(restored_blocks[0]["text"], "What is the time complexity of quicksort in the average case?")
        self.assertEqual(restored_blocks[0]["bounding_box"], (50.0, 100.0, 500.0, 150.0))

        # Check embedding matrix unpacking
        meta_list, matrix = restarted_store.get_all_embeddings(engine_name=self.embedding_engine.engine_name)
        self.assertEqual(len(meta_list), 2)
        self.assertEqual(matrix.shape, (2, 512))
        np.testing.assert_allclose(matrix[0], test_vec, rtol=1e-5)

        restarted_store.close()

    def test_04_content_deduplication_via_sha256(self):
        """Verify that identical documents are detected via file hash to prevent duplicate reprocessing."""
        doc_path = self.temp_dir / "duplicate_test.png"
        img = Image.new("RGB", (200, 200), color="blue")
        img.save(doc_path)

        file_hash = compute_file_sha256(doc_path)
        self.assertIsNone(self.store.get_document_by_hash(file_hash))

        # Save first copy
        self.store.save_document(
            doc_id="doc_first",
            file_path=doc_path,
            file_hash=file_hash,
            file_type="IMAGE",
            page_count=1,
        )

        # Query by hash
        existing = self.store.get_document_by_hash(file_hash)
        self.assertIsNotNone(existing)
        self.assertEqual(existing.doc_id, "doc_first")

    # ==========================================================================
    # Acceptance Test 3 & 4: Grounded Multi-Document Retrieval & Provenance
    # ==========================================================================

    def test_05_grounded_multi_document_retrieval_and_provenance(self):
        """Verify semantic retrieval across multiple documents and guarantee strict provenance."""
        # Ingest Document A: Signal Processing
        doc_a_id = "doc_signal_proc"
        self.store.save_document(
            doc_id=doc_a_id,
            file_path=Path("sample_data/dsp_exam.pdf"),
            file_hash="hash_dsp_001",
            file_type="PDF",
            page_count=1,
        )
        self.store.save_page(page_id=f"{doc_a_id}_p1", doc_id=doc_a_id, page_number=1, width=1000, height=800)

        dsp_text = "What is the computational complexity of performing 2D convolution with a KxK kernel on an HxW image?"
        dsp_vec = self.embedding_engine.embed_texts([dsp_text])[0]
        self.store.save_blocks(
            doc_id=doc_a_id,
            page_number=1,
            blocks_data=[{
                "block_id": 10,
                "block_type": "QUESTION",
                "text": dsp_text,
                "confidence": 0.94,
                "bounding_box": (80.0, 150.0, 920.0, 220.0),
                "embedding": dsp_vec,
                "embedding_engine": self.embedding_engine.engine_name,
            }],
        )

        # Ingest Document B: Operating Systems
        doc_b_id = "doc_operating_systems"
        self.store.save_document(
            doc_id=doc_b_id,
            file_path=Path("sample_data/os_exam.pdf"),
            file_hash="hash_os_002",
            file_type="PDF",
            page_count=1,
        )
        self.store.save_page(page_id=f"{doc_b_id}_p1", doc_id=doc_b_id, page_number=1, width=1000, height=800)

        os_text = "Explain the operating system kernel process scheduling and virtual memory page fault handling."
        os_vec = self.embedding_engine.embed_texts([os_text])[0]
        self.store.save_blocks(
            doc_id=doc_b_id,
            page_number=1,
            blocks_data=[{
                "block_id": 20,
                "block_type": "QUESTION",
                "text": os_text,
                "confidence": 0.91,
                "bounding_box": (60.0, 100.0, 850.0, 180.0),
                "embedding": os_vec,
                "embedding_engine": self.embedding_engine.engine_name,
            }],
        )

        # Query for signal processing / convolution
        retriever = DocumentRetriever(self.store, self.embedding_engine)
        results = retriever.retrieve(
            query="computational complexity of spatial image convolution kernel",
            top_k=2,
            threshold=0.20,
        )

        self.assertGreaterEqual(len(results), 1)

        # Top result MUST be Document A (Signal Processing)
        top = results[0]
        self.assertEqual(top.doc_id, doc_a_id)
        self.assertEqual(top.block_id, 10)
        self.assertIn("convolution", top.text.lower())
        self.assertGreater(top.similarity_score, 0.40)

        # Provenance Guarantee Verification
        self.assertEqual(top.page_number, 1)
        self.assertEqual(top.bounding_box, (80.0, 150.0, 920.0, 220.0))
        self.assertAlmostEqual(top.confidence, 0.94, places=2)
        self.assertEqual(top.block_type, "QUESTION")
        self.assertEqual(top.document_name, "dsp_exam.pdf")

    # ==========================================================================
    # Acceptance Test 5: Token-Budgeted Context Packaging & Citation Format
    # ==========================================================================

    def test_06_token_budgeted_context_synthesis(self):
        """Verify prompt packaging respects token budgets and outputs strict citation tags."""
        synthesizer = EvidenceContextSynthesizer()

        # Create 5 distinct retrieved passages
        passages = [
            RetrievedPassage(
                doc_id="doc_algebra",
                document_name="linear_algebra.pdf",
                page_number=2,
                block_id=3,
                block_type="PARAGRAPH",
                text="The rank of a matrix is the dimension of the vector space generated by its columns.",
                bounding_box=(50.0, 100.0, 450.0, 140.0),
                confidence=0.96,
                similarity_score=0.88,
            ),
            RetrievedPassage(
                doc_id="doc_algebra",
                document_name="linear_algebra.pdf",
                page_number=2,
                block_id=4,
                block_type="PARAGRAPH",
                text="A square matrix is invertible if and only if its determinant is non-zero.",
                bounding_box=(50.0, 150.0, 450.0, 190.0),
                confidence=0.93,
                similarity_score=0.82,
            ),
            RetrievedPassage(
                doc_id="doc_algebra",
                document_name="linear_algebra.pdf",
                page_number=3,
                block_id=1,
                block_type="QUESTION",
                text="Calculate the eigenvalues and eigenvectors of the following 2x2 matrix.",
                bounding_box=(60.0, 80.0, 500.0, 120.0),
                confidence=0.91,
                similarity_score=0.75,
            ),
        ]

        # 1. Test adequate budget (all passages included)
        adequate_ctx = synthesizer.synthesize(
            query="What determines matrix invertibility?",
            passages=passages,
            max_budget_tokens=1000,
        )
        self.assertFalse(adequate_ctx.truncated)
        self.assertEqual(len(adequate_ctx.passages), 3)
        self.assertIn("linear_algebra.pdf", adequate_ctx.formatted_context)
        self.assertIn("[EVIDENCE BLOCK 1]", adequate_ctx.formatted_context)
        self.assertIn("Box: (50.0, 100.0, 450.0, 140.0)", adequate_ctx.formatted_context)

        # 2. Test tight budget truncation
        # Budget sized so only 1 passage fits out of 3
        tight_ctx = synthesizer.synthesize(
            query="What determines matrix invertibility?",
            passages=passages,
            max_budget_tokens=320,
        )
        self.assertTrue(tight_ctx.truncated)
        self.assertEqual(len(tight_ctx.passages), 1)
        self.assertLessEqual(tight_ctx.token_count_estimate, 320)

    # ==========================================================================
    # Acceptance Test 6: End-to-End Pipeline Execution (Mock OCR + Offline Embedding)
    # ==========================================================================

    def test_07_end_to_end_multipage_pipeline(self):
        """Verify full pipeline flow: PDF creation -> Ingestion -> OCR -> Reconstruction -> Store -> Query."""
        pdf_path = self.temp_dir / "exam_test.pdf"
        create_synthetic_pdf(
            pdf_path,
            ["Question 1: Convolution Complexity", "Question 2: Memory Paging"],
            width=600,
            height=400,
        )

        pipeline = DocumentIntelligencePipeline(
            store=self.store,
            ocr_engine=MockOCREngine(),
            embedding_engine=self.embedding_engine,
        )

        # Ingest multi-page document
        stored_doc = pipeline.ingest_document(pdf_path)
        self.assertIsNotNone(stored_doc)
        self.assertEqual(stored_doc.file_name, "exam_test.pdf")
        self.assertEqual(stored_doc.page_count, 2)

        # Verify pages stored
        pages = self.store.get_pages(stored_doc.doc_id)
        self.assertEqual(len(pages), 2)

        # Verify blocks stored
        blocks = self.store.get_blocks(doc_id=stored_doc.doc_id)
        self.assertGreater(len(blocks), 0)

        # Query synthesized context through pipeline
        ctx: SynthesizedContext = pipeline.query(
            query_text="What is the computational complexity of convolution?",
            top_k=2,
            max_budget_tokens=1500,
        )

        self.assertIsNotNone(ctx)
        self.assertIn("VERIFIED CONTEXT EVIDENCE", ctx.formatted_context)
        self.assertGreater(len(ctx.passages), 0)
        self.assertEqual(ctx.passages[0].document_name, "exam_test.pdf")


if __name__ == "__main__":
    unittest.main()
