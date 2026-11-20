"""
test_structure.py: Comprehensive test suite for Module 3 Document Structure Reconstruction.

Covers all 10 evaluation requirements offline without network access or model downloads:
    python -m unittest tests/test_structure.py
"""

import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import (
    BlockType,
    OCRBox,
    OCRResult,
    DocumentStructureResult,
)
from setu_netra.structure.geometry import validate_box, vertical_overlap_ratio
from setu_netra.structure.line_grouper import group_detections_into_lines
from setu_netra.structure.block_grouper import group_lines_into_blocks
from setu_netra.structure.reconstructor import DocumentStructureReconstructor


def make_box(
    text: str,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    conf: float = 0.90,
) -> OCRBox:
    """Helper to construct an OCRBox from rectangular coordinates."""
    polygon = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))
    return OCRBox(polygon=polygon, text=text, confidence=conf)


class TestDocumentStructureReconstruction(unittest.TestCase):
    """Test suite covering the 10 required document reconstruction scenarios."""

    def setUp(self):
        self.reconstructor = DocumentStructureReconstructor()

    # 1. Grouping OCR detections into lines
    def test_01_grouping_ocr_detections_into_lines(self):
        # 3 horizontal tokens on the same line with vertical baseline jitter
        b1 = make_box("What", xmin=50.0, ymin=100.0, xmax=90.0, ymax=120.0)
        b2 = make_box("is", xmin=95.0, ymin=102.0, xmax=115.0, ymax=122.0)
        b3 = make_box("computational", xmin=120.0, ymin=98.0, xmax=220.0, ymax=118.0)

        lines, order_indices, warnings = group_detections_into_lines([b1, b2, b3])

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].text, "What is computational")
        self.assertEqual(lines[0].box_indices, (0, 1, 2))
        self.assertEqual(lines[0].xmin, 50.0)
        self.assertEqual(lines[0].xmax, 220.0)
        self.assertEqual(order_indices, [0, 1, 2])

    # 2. Grouping lines into blocks
    def test_02_grouping_lines_into_blocks(self):
        # 2 lines close together (paragraph lines, vertical gap = 6px)
        # Followed by a 3rd line with large gap (50px gap)
        b1 = make_box("This is the first sentence of", 50, 100, 300, 120)
        b2 = make_box("the introductory paragraph.", 50, 126, 280, 146)
        b3 = make_box("This is a new section block.", 50, 200, 290, 220)

        lines, _, _ = group_detections_into_lines([b1, b2, b3])
        blocks = group_lines_into_blocks(lines)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(len(blocks[0]), 2)  # b1 and b2 form first block
        self.assertEqual(len(blocks[1]), 1)  # b3 forms second block

    # 3. Reconstructing multiple questions
    def test_03_reconstructing_multiple_questions(self):
        boxes = [
            # Question 1 with options A and B
            make_box("Q1: What is 2 + 2?", 50, 50, 200, 70),
            make_box("[A] 3", 60, 80, 100, 95),
            make_box("[B] 4", 60, 105, 100, 120),
            # Question 2 with options A, B, and C
            make_box("Q2: What is 3 * 3?", 50, 160, 200, 180),
            make_box("[A] 6", 60, 190, 100, 205),
            make_box("[B] 9", 60, 215, 100, 230),
            make_box("[C] 12", 60, 240, 100, 255),
        ]

        result = self.reconstructor.reconstruct(boxes)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.questions), 2)
        # Check Question 1
        q1 = result.questions[0]
        self.assertEqual(q1.question_number, "1")
        self.assertIn("2 + 2", q1.question_text)
        self.assertEqual(len(q1.options), 2)
        self.assertEqual(q1.options[0].option_label, "A")
        self.assertEqual(q1.options[1].option_label, "B")

        # Check Question 2
        q2 = result.questions[1]
        self.assertEqual(q2.question_number, "2")
        self.assertIn("3 * 3", q2.question_text)
        self.assertEqual(len(q2.options), 3)
        self.assertEqual(q2.options[0].option_label, "A")
        self.assertEqual(q2.options[1].option_label, "B")
        self.assertEqual(q2.options[2].option_label, "C")

    # 4. Associating answer options with questions
    def test_04_associating_answer_options_with_questions(self):
        boxes = [
            make_box("What is the capital of France?", 50, 50, 300, 70),
            make_box("[A] Berlin", 60, 80, 130, 95),
            make_box("[B] Madrid", 60, 105, 130, 120),
            make_box("[C] Paris", 60, 130, 130, 145),
            make_box("[D] Rome", 60, 155, 130, 170),
        ]

        result = self.reconstructor.reconstruct(boxes)

        self.assertEqual(len(result.questions), 1)
        q = result.questions[0]
        self.assertEqual(len(q.options), 4)
        labels = [opt.option_label for opt in q.options]
        self.assertEqual(labels, ["A", "B", "C", "D"])

        # Check that each option block records its parent question block ID
        opt_blocks = [b for b in result.blocks if b.block_type == BlockType.OPTION]
        self.assertEqual(len(opt_blocks), 4)
        for opt_b in opt_blocks:
            self.assertEqual(opt_b.role_metadata.get("parent_question_id"), q.question_block_id)

    # 5. Handling paragraphs and lists
    def test_05_handling_paragraphs_and_lists(self):
        boxes = [
            # Narrative paragraph
            make_box("Optical Character Recognition converts pixel bitmaps into unicode text.", 50, 50, 450, 68),
            # Numbered list items (NOT questions!)
            make_box("1. Validate image format and dimensions.", 50, 100, 320, 118),
            make_box("2. Perform grayscale conversion and contrast tuning.", 50, 128, 380, 146),
            # Bullet list items
            make_box("• First observation", 50, 180, 200, 198),
            make_box("• Second observation", 50, 208, 210, 226),
        ]

        result = self.reconstructor.reconstruct(boxes)

        # Should NOT classify declarative numbered or bulleted items as questions
        self.assertEqual(len(result.questions), 0)
        types = [b.block_type for b in result.blocks]
        self.assertIn(BlockType.PARAGRAPH, types)
        self.assertIn(BlockType.LIST_ITEM, types)
        self.assertNotIn(BlockType.QUESTION, types)

    # 6. Handling documents without questions
    def test_06_handling_documents_without_questions(self):
        boxes = [
            make_box("SETU-NETRA SYSTEM ARCHITECTURE", 50, 30, 350, 50),
            make_box("This document outlines the pipeline flow from ingestion to OCR.", 50, 70, 450, 90),
            make_box("Note: All processing runs locally on CPU.", 50, 120, 350, 140),
        ]

        result = self.reconstructor.reconstruct(boxes)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.questions), 0)
        self.assertEqual(result.metadata.get("total_questions"), 0)
        self.assertEqual(result.metadata.get("document_type_hint"), "GENERAL_TEXT_DOCUMENT")
        types = [b.block_type for b in result.blocks]
        self.assertEqual(types, [BlockType.HEADING, BlockType.PARAGRAPH, BlockType.NOTE])

    # 7. Preserving uncertain OCR output
    def test_07_preserving_uncertain_ocr_output(self):
        # OCR box with very low confidence (e.g. 0.15)
        noisy_box = make_box("~#%x&", 50, 100, 120, 120, conf=0.15)
        valid_box = make_box("Valid Text Line", 50, 150, 200, 170, conf=0.92)

        result = self.reconstructor.reconstruct([noisy_box, valid_box])

        # Text and confidence must be preserved exactly
        block_noisy = result.blocks[0]
        self.assertEqual(block_noisy.text, "~#%x&")
        self.assertEqual(block_noisy.mean_confidence, 0.15)
        self.assertEqual(block_noisy.block_type, BlockType.UNCLASSIFIED)
        self.assertIn("low_confidence_detection", block_noisy.warnings)

    # 8. Handling missing or invalid coordinates
    def test_08_handling_missing_or_invalid_coordinates(self):
        # Create boxes with degenerate coordinates: width=0, height=0, NaN, or empty polygon
        good_box = make_box("Valid Detection", 50, 50, 150, 70)
        zero_w_box = make_box("Zero Width", 100, 50, 100, 70)
        zero_h_box = make_box("Zero Height", 50, 100, 150, 100)
        nan_box = OCRBox(
            polygon=((float("nan"), 50.0), (150.0, 50.0), (150.0, 70.0), (50.0, 70.0)),
            text="NaN Box",
            confidence=0.5,
        )
        empty_poly_box = OCRBox(polygon=(), text="Empty Poly", confidence=0.5)

        result = self.reconstructor.reconstruct([good_box, zero_w_box, zero_h_box, nan_box, empty_poly_box])

        # Pipeline must NOT crash, degenerate boxes must be flagged in warnings
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.blocks), 1)
        self.assertEqual(result.blocks[0].text, "Valid Detection")
        self.assertGreaterEqual(len(result.warnings), 4)

    # 9. Handling ambiguous question numbering
    def test_09_handling_ambiguous_question_numbering(self):
        # Options with a missing label: A, C, D (missing B!)
        boxes = [
            make_box("Which protocol is connection-oriented?", 50, 50, 350, 70),
            make_box("[A] TCP", 60, 80, 120, 95),
            make_box("[C] UDP", 60, 105, 120, 120),
            make_box("[D] ICMP", 60, 130, 120, 145),
        ]

        result = self.reconstructor.reconstruct(boxes)

        self.assertEqual(len(result.questions), 1)
        q = result.questions[0]
        self.assertEqual(len(q.options), 3)
        # Warning must flag the non-consecutive options
        self.assertTrue(any("missing label" in w or "Non-consecutive" in w for w in q.warnings))

    # 10. Preserving reading order
    def test_10_preserving_reading_order(self):
        # Supply boxes in reverse vertical order and shuffled horizontal order
        b_bottom = make_box("Line 3 at bottom", 50, 300, 200, 320)
        b_mid_right = make_box("World!", 120, 200, 180, 220)
        b_mid_left = make_box("Hello", 50, 200, 110, 220)
        b_top = make_box("Line 1 at top", 50, 100, 180, 120)

        shuffled = [b_bottom, b_mid_right, b_mid_left, b_top]
        result = self.reconstructor.reconstruct(shuffled)

        block_texts = [b.text for b in result.blocks]
        self.assertEqual(block_texts[0], "Line 1 at top")
        self.assertEqual(block_texts[1], "Hello World!")
        self.assertEqual(block_texts[2], "Line 3 at bottom")


if __name__ == "__main__":
    unittest.main()
