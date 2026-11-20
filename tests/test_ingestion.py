"""
Unit tests for SETU-NETRA Milestone 1: Ingestion, Validation, and Preprocessing.

Runs with both standard library unittest and pytest:
    python -m unittest discover -s tests
    or
    pytest tests/
"""

import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import PreprocessConfig
from setu_netra.ingestion.validator import validate_image_file
from setu_netra.ingestion.loader import extract_metadata, load_image
from setu_netra.preprocessing.operations import (
    to_grayscale,
    resize_keep_aspect_ratio,
    adjust_contrast,
)
from setu_netra.preprocessing.pipeline import ImagePreprocessor


class TestIngestionAndPreprocessing(unittest.TestCase):
    """Test suite for Milestone 1 modules."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_dummy_image(self, path: Path, size=(400, 200), color=(100, 150, 200)) -> Path:
        img = Image.new("RGB", size, color=color)
        img.save(path, format="PNG")
        return path

    def test_validation_rejects_missing_file(self):
        non_existent = self.tmp_path / "does_not_exist.jpg"
        result = validate_image_file(non_existent)
        self.assertFalse(result.is_valid)
        self.assertIn("does not exist", result.error_message.lower())

    def test_validation_rejects_unsupported_extension(self):
        text_file = self.tmp_path / "test.txt"
        text_file.write_text("Hello world")
        result = validate_image_file(text_file)
        self.assertFalse(result.is_valid)
        self.assertIn("unsupported file extension", result.error_message.lower())

    def test_validation_rejects_empty_file(self):
        empty_file = self.tmp_path / "empty.png"
        empty_file.touch()
        result = validate_image_file(empty_file)
        self.assertFalse(result.is_valid)
        self.assertIn("empty", result.error_message.lower())

    def test_validation_accepts_valid_image(self):
        img_path = self.tmp_path / "valid.png"
        self._create_dummy_image(img_path)
        result = validate_image_file(img_path)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.error_message)

    def test_extract_metadata(self):
        img_path = self.tmp_path / "meta_test.png"
        self._create_dummy_image(img_path, size=(600, 300))
        with Image.open(img_path) as img:
            meta = extract_metadata(img, img_path)

        self.assertEqual(meta.width, 600)
        self.assertEqual(meta.height, 300)
        self.assertEqual(meta.color_mode, "RGB")
        self.assertEqual(meta.channels, 3)
        self.assertEqual(meta.aspect_ratio, 2.0)
        # Memory calculation: 600 * 300 * 3 = 540,000 bytes
        self.assertEqual(meta.estimated_memory_bytes, 540000)

    def test_to_grayscale(self):
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        gray = to_grayscale(img)

        self.assertEqual(img.mode, "RGB", "Original image must not be mutated in-place")
        self.assertEqual(gray.mode, "L", "Transformed image must be in single-channel 'L' mode")
        self.assertEqual(gray.size, (100, 100))

    def test_resize_keep_aspect_ratio(self):
        # 2000 x 1000 image (2:1 aspect ratio)
        img = Image.new("RGB", (2000, 1000), color=(200, 200, 200))
        resized, was_resized = resize_keep_aspect_ratio(img, max_dimension=1000)

        self.assertTrue(was_resized)
        self.assertEqual(resized.size, (100, 500) if False else (1000, 500))
        self.assertEqual(img.size, (2000, 1000), "Original image size must not be changed")

        # When image is already smaller than max_dimension, it should not resize
        no_change, was_resized_2 = resize_keep_aspect_ratio(resized, max_dimension=1500)
        self.assertFalse(was_resized_2)
        self.assertEqual(no_change.size, (1000, 500))

    def test_contrast_adjustment(self):
        img = Image.new("L", (100, 100), color=128)
        enhanced = adjust_contrast(img, factor=1.5)
        self.assertEqual(enhanced.size, img.size)
        self.assertIsNot(enhanced, img, "Enhanced image must be a distinct object")

    def test_preprocessor_pipeline_preserves_original(self):
        img_path = self.tmp_path / "pipeline_test.png"
        self._create_dummy_image(img_path, size=(2400, 1200))
        orig_bytes = img_path.read_bytes()

        img, meta = load_image(img_path)
        output_dir = self.tmp_path / "out"

        config = PreprocessConfig(
            convert_grayscale=True,
            max_dimension=1200,
            contrast_factor=1.4,
        )
        preprocessor = ImagePreprocessor(config=config)
        result = preprocessor.process(img, meta, output_dir=output_dir)

        # 1. Check result metadata
        self.assertEqual(result.processed_metadata.color_mode, "L")
        self.assertEqual(result.processed_metadata.width, 1200)
        self.assertEqual(result.processed_metadata.height, 600)

        # 2. Check output file existence
        self.assertIsNotNone(result.output_path)
        self.assertTrue(result.output_path.exists())

        # 3. Verify original file on disk was completely untouched (byte-for-byte identical)
        self.assertEqual(img_path.read_bytes(), orig_bytes)


if __name__ == "__main__":
    unittest.main()
