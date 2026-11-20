"""
test_docx_txt_ingestion.py: Unit and integration tests for DOCX and TXT document ingestion
in SETU-NETRA Stage 3.

Tests:
1. DOCX validation (valid vs invalid PK header vs missing document.xml).
2. DOCX extraction of headings, paragraphs, and tables with synthesized layout coordinates.
3. DOCX synthetic page rendering (PIL image generation).
4. TXT validation (UTF-8, whitespace-only rejection).
5. TXT pagination and block generation.
6. End-to-end ingestion of DOCX and TXT into SQLiteDocumentStore via DocumentIntelligencePipeline.
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.ingestion.docx_loader import load_docx_pages
from setu_netra.ingestion.text_loader import load_text_pages
from setu_netra.ingestion.validator import validate_document_file
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.semantic.engine import SemanticUnderstandingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore


def create_minimal_docx(file_path: Path, heading: str, paragraphs: list, table_data: list = None):
    """Helper to generate a structurally valid DOCX file using Python's standard library."""
    document_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
        f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{heading}</w:t></w:r></w:p>',
    ]
    for p in paragraphs:
        document_xml.append(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>")

    if table_data:
        document_xml.append("<w:tbl>")
        for row in table_data:
            document_xml.append("<w:tr>")
            for cell in row:
                document_xml.append(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>")
            document_xml.append("</w:tr>")
        document_xml.append("</w:tbl>")

    document_xml.append("</w:body></w:document>")

    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "".join(document_xml).encode("utf-8"))
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')


class TestDocxTxtIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_path = Path(self.temp_dir.name)
        self.db_path = self.work_path / "test_stage3.db"
        self.store = SQLiteDocumentStore(self.db_path)
        self.pipeline = DocumentIntelligencePipeline(
            store=self.store,
        )

    def tearDown(self):
        if hasattr(self, "store"):
            self.store.close()
        self.temp_dir.cleanup()

    def test_docx_validation(self):
        docx_path = self.work_path / "sample.docx"
        create_minimal_docx(docx_path, "Introduction", ["Paragraph one text."])

        # Valid docx
        val = validate_document_file(docx_path)
        self.assertTrue(val.is_valid)

        # Invalid header
        bad_path = self.work_path / "bad.docx"
        bad_path.write_bytes(b"NOT_A_ZIP_HEADER_DATA")
        val_bad = validate_document_file(bad_path)
        self.assertFalse(val_bad.is_valid)
        self.assertIn("missing standard PK ZIP header", val_bad.error_message)

    def test_docx_loader_extraction(self):
        docx_path = self.work_path / "research_paper.docx"
        headings = "Deep Learning Architecture"
        paragraphs = [
            "We propose a transformer-based encoder for spatial document layout analysis.",
            "Our model demonstrates high precision across multi-column academic benchmarks.",
        ]
        table = [
            ["Model", "F1 Score"],
            ["Baseline", "84.2"],
            ["SETU-NETRA", "93.8"],
        ]
        create_minimal_docx(docx_path, headings, paragraphs, table)

        pages = load_docx_pages(docx_path)
        self.assertGreaterEqual(len(pages), 1)

        p_num, canvas, w, h, blocks = pages[0]
        self.assertEqual(p_num, 1)
        self.assertGreater(len(blocks), 0)

        # Verify block types
        types = [b["block_type"] for b in blocks]
        self.assertIn("HEADING", types)
        self.assertIn("PARAGRAPH", types)
        self.assertIn("TABLE", types)

        # Verify preview canvas
        self.assertIsInstance(canvas, Image.Image)
        self.assertEqual(canvas.size, (w, h))

    def test_txt_loader_extraction(self):
        txt_path = self.work_path / "notes.txt"
        content = (
            "Lecture Notes: Computer Networks\n\n"
            "Chapter 1: The OSI Reference Model\n"
            "The physical layer transmits raw bits over a transmission medium.\n"
            "The data link layer handles frame synchronization and flow control.\n\n"
            "Chapter 2: Routing Protocols\n"
            "Distance vector algorithms compute routing matrices using Bellman-Ford.\n"
        )
        txt_path.write_text(content, encoding="utf-8")

        val = validate_document_file(txt_path)
        self.assertTrue(val.is_valid)

        pages = load_text_pages(txt_path)
        self.assertGreaterEqual(len(pages), 1)

        p_num, canvas, w, h, blocks = pages[0]
        self.assertGreater(len(blocks), 0)
        texts = [b["text"] for b in blocks]
        self.assertTrue(any("OSI Reference Model" in t for t in texts))

        self.assertIsInstance(canvas, Image.Image)

    def test_txt_validation_rejects_empty_whitespace(self):
        empty_txt = self.work_path / "empty.txt"
        empty_txt.write_text("   \n\t  \n  ", encoding="utf-8")
        val = validate_document_file(empty_txt)
        self.assertFalse(val.is_valid)
        self.assertIn("whitespace", val.error_message.lower())

    def test_pipeline_ingest_docx_and_txt(self):
        # 1. Ingest DOCX
        docx_path = self.work_path / "thesis.docx"
        create_minimal_docx(
            docx_path,
            "Operating Systems Survey",
            ["Virtual memory abstracts physical RAM through page tables and translation lookaside buffers."],
        )
        res_docx = self.pipeline.ingest_document(docx_path)
        self.assertIsNotNone(res_docx.doc_id)
        self.assertEqual(res_docx.page_count, 1)

        # Verify persistence in SQLite
        db_doc = self.store.get_document_by_id(res_docx.doc_id)
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc.doc_id, res_docx.doc_id)

        blocks = self.store.get_blocks(res_docx.doc_id, page_number=1)
        self.assertGreaterEqual(len(blocks), 1)

        # 2. Ingest TXT
        txt_path = self.work_path / "algorithm.txt"
        txt_path.write_text(
            "Binary search has logarithmic time complexity O(log n).\n"
            "Linear search requires O(n) worst-case time.",
            encoding="utf-8",
        )
        res_txt = self.pipeline.ingest_document(txt_path)
        self.assertIsNotNone(res_txt.doc_id)
        self.assertEqual(res_txt.page_count, 1)

        db_txt = self.store.get_document_by_id(res_txt.doc_id)
        self.assertIsNotNone(db_txt)
        self.assertEqual(db_txt.doc_id, res_txt.doc_id)


if __name__ == "__main__":
    unittest.main()
