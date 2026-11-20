"""
test_ocr.py: Automated test suite for Milestone 2 OCR subsystem.

Runs completely offline without downloading heavy model weights:
    python -m unittest tests/test_ocr.py
"""

import sys
import unittest
from pathlib import Path
from PIL import Image

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import OCRBox, OCRConfig, OCRResult
from setu_netra.ocr.base import BaseOCREngine, OCREngineError, OCREngineNotFoundError
from setu_netra.ocr.mock_engine import MockOCREngine
from setu_netra.ocr.easyocr_engine import EasyOCREngine
from setu_netra.ocr.factory import get_ocr_engine


class TestOCRSubsystem(unittest.TestCase):
    """Test suite for OCR contracts, mock engine, and engine factory."""

    def test_ocr_box_geometry_calculations(self):
        # Quadrilateral box from (10, 20) to (110, 60)
        polygon = ((10.0, 20.0), (110.0, 20.0), (110.0, 60.0), (10.0, 60.0))
        box = OCRBox(polygon=polygon, text="Test Word", confidence=0.95)

        self.assertEqual(box.xmin, 10.0)
        self.assertEqual(box.ymin, 20.0)
        self.assertEqual(box.xmax, 110.0)
        self.assertEqual(box.ymax, 60.0)
        self.assertEqual(box.width, 100.0)
        self.assertEqual(box.height, 40.0)
        self.assertEqual(box.center, (60.0, 40.0))
        self.assertEqual(box.text, "Test Word")
        self.assertEqual(box.confidence, 0.95)

    def test_mock_engine_interface_contract(self):
        engine = MockOCREngine()
        self.assertIsInstance(engine, BaseOCREngine)
        self.assertEqual(engine.engine_name, "mock")
        self.assertTrue(engine.is_available())

    def test_mock_engine_inference_on_synthetic_image(self):
        # 1200 x 800 non-uniform image
        img = Image.new("RGB", (1200, 800), color=(255, 255, 255))
        # Add contrast so it's not a blank canvas
        img.putpixel((50, 50), (0, 0, 0))

        engine = MockOCREngine()
        result = engine.recognize(img)

        self.assertIsInstance(result, OCRResult)
        self.assertEqual(result.status, "SUCCESS")
        self.assertGreater(len(result.boxes), 0)
        self.assertIn("Q.1)", result.raw_text)
        self.assertGreater(result.processing_time_ms, 0.0)

    def test_mock_engine_empty_result_on_uniform_image(self):
        # Completely uniform 100x100 white image
        blank_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        engine = MockOCREngine()
        result = engine.recognize(blank_img)

        self.assertEqual(result.status, "EMPTY")
        self.assertEqual(len(result.boxes), 0)
        self.assertEqual(result.raw_text, "")
        self.assertIsNotNone(result.error_message)

    def test_ocr_preserves_input_image_unmutated(self):
        img = Image.new("RGB", (200, 100), color=(120, 140, 160))
        pixel_before = img.getpixel((10, 10))

        engine = MockOCREngine()
        _ = engine.recognize(img)

        self.assertEqual(img.size, (200, 100))
        self.assertEqual(img.getpixel((10, 10)), pixel_before, "OCR must not alter pixel values")

    def test_factory_returns_mock_engine(self):
        engine = get_ocr_engine("mock")
        self.assertIsInstance(engine, MockOCREngine)

    def test_factory_rejects_unknown_engine(self):
        with self.assertRaises(OCREngineNotFoundError) as ctx:
            get_ocr_engine("non_existent_engine_xyz")
        self.assertIn("unsupported ocr engine", str(ctx.exception).lower())

    def test_confidence_threshold_filtering(self):
        img = Image.new("RGB", (800, 600), color=(240, 240, 240))
        img.putpixel((10, 10), (0, 0, 0))

        # Set high confidence threshold that filters out lower confidence tokens
        strict_config = OCRConfig(engine_name="mock", confidence_threshold=0.96)
        engine = MockOCREngine(config=strict_config)
        result = engine.recognize(img)

        for box in result.boxes:
            self.assertGreaterEqual(box.confidence, 0.96)

    def test_ocr_config_handwriting_parameters(self):
        config = OCRConfig(
            add_margin=0.20,
            mag_ratio=1.5,
            link_threshold=0.25,
            text_threshold=0.50,
            paragraph=True,
        )
        self.assertEqual(config.add_margin, 0.20)
        self.assertEqual(config.mag_ratio, 1.5)
        self.assertEqual(config.link_threshold, 0.25)
        self.assertEqual(config.text_threshold, 0.50)
        self.assertTrue(config.paragraph)


if __name__ == "__main__":
    unittest.main()
