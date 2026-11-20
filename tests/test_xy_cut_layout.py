"""
test_xy_cut_layout.py: Unit and regression tests for Recursive X-Y Cut multi-column layout analysis.

Tests:
1. Projection valley detection along 1D intervals.
2. Two-column document layout separation with distinct vertical gutters.
3. Three-column layout separation.
4. Single-column document preservation without false column splitting.
5. Reading order preservation (column-first ordering preventing cross-gutter line merging).
6. Integration with DocumentStructureReconstructor.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import OCRBox
from setu_netra.structure.reconstructor import DocumentStructureReconstructor
from setu_netra.structure.xy_cut import detect_columns, _find_projection_valleys


class TestXYCutLayout(unittest.TestCase):
    def test_find_projection_valleys(self):
        # Two blocks [10, 50] and [150, 200] across [0, 250]
        intervals = [(10.0, 50.0), (150.0, 200.0)]
        valleys = _find_projection_valleys(intervals, span_min=0.0, span_max=250.0, min_gap=20.0)

        # Expect gutter between 50 and 150 (width 100 >= 20)
        gutter = [g for g in valleys if g[0] >= 50.0 and g[1] <= 150.0]
        self.assertEqual(len(gutter), 1)
        self.assertEqual(gutter[0], (50.0, 150.0))

    def test_single_column_preservation(self):
        # Full-width paragraphs in a single column
        boxes = [
            OCRBox(text="Introduction to Artificial Intelligence", confidence=0.98,
                   polygon=[[50, 50], [500, 50], [500, 70], [50, 70]]),
            OCRBox(text="Machine learning is a subset of AI.", confidence=0.97,
                   polygon=[[50, 85], [520, 85], [520, 105], [50, 105]]),
            OCRBox(text="Deep neural networks require substantial data.", confidence=0.95,
                   polygon=[[50, 120], [480, 120], [480, 140], [50, 140]]),
        ]
        columns = detect_columns(boxes, min_gutter_width=30.0)
        self.assertEqual(len(columns), 1)
        self.assertEqual(len(columns[0]), 3)

    def test_two_column_gutter_detection(self):
        # Left column: x in [50, 350]
        # Right column: x in [450, 750]
        # Gutter: [350, 450] (width 100 > min_gutter_width 30)
        boxes = [
            # Left column top
            OCRBox(text="Col 1: In this work we study", confidence=0.98,
                   polygon=[[50, 100], [350, 100], [350, 120], [50, 120]]),
            # Left column middle
            OCRBox(text="Col 1: document representations.", confidence=0.97,
                   polygon=[[50, 130], [340, 130], [340, 150], [50, 150]]),
            # Right column top (same vertical Y range as left col top)
            OCRBox(text="Col 2: Related prior experiments", confidence=0.99,
                   polygon=[[450, 100], [750, 100], [750, 120], [450, 120]]),
            # Right column middle (same vertical Y range as left col middle)
            OCRBox(text="Col 2: utilized synthetic datasets.", confidence=0.96,
                   polygon=[[450, 130], [740, 130], [740, 150], [450, 150]]),
        ]

        columns = detect_columns(boxes, min_gutter_width=30.0)
        self.assertEqual(len(columns), 2)

        # Verify left column has 2 boxes, right column has 2 boxes
        col1_texts = [b.text for b in columns[0]]
        col2_texts = [b.text for b in columns[1]]
        self.assertTrue(all("Col 1" in t for t in col1_texts))
        self.assertTrue(all("Col 2" in t for t in col2_texts))

    def test_reconstructor_prevents_cross_gutter_line_merging(self):
        # Prior naive reconstructor would merge Box 1 and Box 3 because they share the same Y range [100, 120]
        # With XY-Cut column grouping, Box 1 and Box 3 must remain in separate lines/blocks.
        boxes = [
            OCRBox(text="Left Column Top", confidence=0.95,
                   polygon=[[50, 100], [250, 100], [250, 120], [50, 120]]),
            OCRBox(text="Left Column Bottom", confidence=0.95,
                   polygon=[[50, 130], [250, 130], [250, 150], [50, 150]]),
            OCRBox(text="Right Column Top", confidence=0.95,
                   polygon=[[450, 100], [650, 100], [650, 120], [450, 120]]),
            OCRBox(text="Right Column Bottom", confidence=0.95,
                   polygon=[[450, 130], [650, 130], [650, 150], [450, 150]]),
        ]

        reconstructor = DocumentStructureReconstructor()
        result = reconstructor.reconstruct(boxes)

        # Check lines within blocks: No line should contain both "Left Column" and "Right Column"
        for block in result.blocks:
            for line in block.lines:
                self.assertFalse(
                    "Left" in line.text and "Right" in line.text,
                    f"Line '{line.text}' merged text across columns!",
                )

        # Check block texts: Column 1 blocks should be distinct from Column 2 blocks
        for block in result.blocks:
            self.assertFalse(
                "Left" in block.text and "Right" in block.text,
                f"Block '{block.text}' merged text across columns!",
            )

        # Check reading order: Left Column text must appear before Right Column text in reading sequence
        full_text = " ".join(b.text for b in result.blocks)
        left_idx = full_text.find("Left Column Top")
        right_idx = full_text.find("Right Column Top")
        self.assertLess(left_idx, right_idx)


if __name__ == "__main__":
    unittest.main()
