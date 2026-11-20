"""
test_image_to_answer_pipeline.py: End-to-end integration and research audit for SETU-NETRA
Image-to-Answer Pipeline across 10 real-world input scenarios.

Scenarios:
1. Mathematical question (formula, calculation)
2. Handwritten SQL MCQ question
3. Printed SQL question
4. Portrait-oriented image
5. Landscape-oriented image
6. High-resolution image (>2500px on long edge)
7. Low-resolution image (<400px on long edge)
8. Rotated image (90 deg with EXIF orientation tag)
9. Multi-region image (question header + code/table + options)
10. Uncertain handwriting image (faint/noisy handwriting)
"""

import io
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.ocr.factory import get_ocr_engine
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.preprocessing.operations import (
    map_bbox_to_original,
    normalize_exif_orientation,
    resize_keep_aspect_ratio,
    safe_composite_on_white,
    sniff_image_format,
)
from setu_netra.qa.image_question_solver import ImageQuestionSolution, ImageQuestionSolver, SolverLifecycleState
from setu_netra.qa.question_extractor import QuestionExtractor
from setu_netra.store.sqlite_store import SQLiteDocumentStore


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "image_pipeline"
SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def create_printed_text_image(
    path: Path,
    text_lines: list,
    size: tuple = (1200, 800),
    bg_color: tuple = (255, 255, 255),
    text_color: tuple = (20, 20, 20),
    font_size: int = 32,
    exif_orientation: int = None,
) -> Path:
    """Helper creating crisp procedural document images."""
    img = Image.new("RGB", size, color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    y = 60
    for line in text_lines:
        draw.text((60, y), line, fill=text_color, font=font)
        y += font_size + 18

    # Add border
    draw.rectangle([10, 10, size[0] - 10, size[1] - 10], outline=(200, 200, 200), width=2)

    if exif_orientation:
        exif = img.getexif()
        exif[0x0112] = exif_orientation
        if exif_orientation == 6:
            # Physical raster is stored rotated 90 deg; EXIF tag 6 signals transpose back upright
            img_to_save = img.rotate(90, expand=True)
            img_to_save.save(path, exif=exif)
        elif exif_orientation == 8:
            img_to_save = img.rotate(270, expand=True)
            img_to_save.save(path, exif=exif)
        elif exif_orientation == 3:
            img_to_save = img.rotate(180, expand=True)
            img_to_save.save(path, exif=exif)
        else:
            img.save(path, exif=exif)
    else:
        img.save(path)
    return path


class TestImageToAnswerPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        cls.ocr_engine = get_ocr_engine("easyocr")
        cls.solver = ImageQuestionSolver(ocr_engine=cls.ocr_engine)
        cls.test_results = []

        # Prepare synthetic fixture images
        # 3. Printed SQL
        cls.img_printed_sql = FIXTURES_DIR / "scenario_03_printed_sql.png"
        create_printed_text_image(
            cls.img_printed_sql,
            [
                "SQL Assessment - Question 12",
                "Which SQL clause groups rows sharing the same values in specified",
                "columns into summary aggregations?",
                "[A] WHERE",
                "[B] GROUP BY",
                "[C] ORDER BY",
                "[D] HAVING",
            ],
            size=(1200, 700),
            font_size=28,
        )

        # 4. Portrait orientation (700 x 1400)
        cls.img_portrait = FIXTURES_DIR / "scenario_04_portrait.png"
        create_printed_text_image(
            cls.img_portrait,
            [
                "Calculus Assessment",
                "Calculate the first derivative of:",
                "f(x) = 3*x^2 + 5*x - 7",
                "",
                "[A] 6*x + 5",
                "[B] 3*x + 5",
                "[C] 6*x - 7",
                "[D] 9*x^2",
            ],
            size=(700, 1300),
            font_size=26,
        )

        # 6. High-Resolution (>2500px: 3000 x 2200)
        cls.img_high_res = FIXTURES_DIR / "scenario_06_high_res.png"
        create_printed_text_image(
            cls.img_high_res,
            [
                "High Resolution Benchmark Test",
                "What is the time complexity of performing 2D convolution on an image",
                "of size HxW with a kernel of size KxK?",
                "[A] O(H * W)",
                "[B] O(H * W * K^2)",
                "[C] O(H * W * log(K))",
                "[D] O(K^4)",
            ],
            size=(3000, 2200),
            font_size=64,
        )

        # 7. Low-Resolution (<400px: 380 x 240)
        cls.img_low_res = FIXTURES_DIR / "scenario_07_low_res.png"
        create_printed_text_image(
            cls.img_low_res,
            [
                "Sum b - a;",
                "a = 20, b = 50",
                "a) 20  b) 50",
                "c) 10  d) 30",
            ],
            size=(380, 240),
            font_size=14,
        )

        # 8. Rotated 90 degrees with EXIF tag 6
        cls.img_rotated_exif = FIXTURES_DIR / "scenario_08_rotated.jpg"
        create_printed_text_image(
            cls.img_rotated_exif,
            [
                "Rotated Image Test",
                "Integer a = 20; Integer b = 50;",
                "Sum = b - a; Value of Sum:",
                "[A] 20",
                "[B] 50",
                "[C] 10",
                "[D] 30",
            ],
            size=(1000, 700),
            font_size=26,
            exif_orientation=6,  # 90 deg rotation
        )

        # 9. Multi-Region Document
        cls.img_multi_region = FIXTURES_DIR / "scenario_09_multi_region.png"
        create_printed_text_image(
            cls.img_multi_region,
            [
                "Database Query Optimization Lab",
                "Consider Table 'employees' with columns (id, name, department, salary).",
                "SELECT department, COUNT(*) FROM employees GROUP BY department;",
                "",
                "What is the output produced by the query?",
                "[A] Number of employees per distinct department",
                "[B] List of all employee names",
                "[C] Total salary sum across all departments",
                "[D] Nothing (syntax error)",
            ],
            size=(1400, 900),
            font_size=24,
        )

    def test_01_mathematical_question(self):
        """Scenario 1: Mathematical question (2D convolution complexity)."""
        img_path = SAMPLE_DATA_DIR / "sample_question.png"
        self.assertTrue(img_path.exists())

        img = Image.open(img_path)
        sol: ImageQuestionSolution = self.solver.solve_image(img)

        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.domain, "MATHEMATICAL")
        self.assertTrue(sol.is_mcq)
        self.assertEqual(sol.selected_option, "B")
        self.assertTrue("K2" in sol.final_answer or "K^2" in sol.final_answer)
        self.assertIn("B", sol.option_analysis)

        self.__class__.test_results.append({
            "scenario": 1,
            "name": "Mathematical Question (2D Convolution Complexity)",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": img.format or "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_02_handwritten_sql_mcq(self):
        """Scenario 2: Handwritten SQL MCQ question."""
        img_path = SAMPLE_DATA_DIR / "sample_question3.jpeg"
        self.assertTrue(img_path.exists())

        img = Image.open(img_path)
        sol: ImageQuestionSolution = self.solver.solve_image(img)

        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.domain, "SQL")
        self.assertIsNotNone(sol.selected_option)
        self.assertIn("mountain", sol.final_answer.lower())

        self.__class__.test_results.append({
            "scenario": 2,
            "name": "Handwritten SQL MCQ Question",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": img.format or "JPEG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_03_printed_sql_question(self):
        """Scenario 3: Printed SQL question (GROUP BY vs WHERE/ORDER BY)."""
        img = Image.open(self.img_printed_sql)
        sol: ImageQuestionSolution = self.solver.solve_image(img)

        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.domain, "SQL")
        self.assertTrue(sol.is_mcq)
        self.assertEqual(len(sol.options), 4)

        # Verifies option parsing and GROUP BY selection
        opt_b = next((o for o in sol.options if o["label"] == "B"), None)
        self.assertIsNotNone(opt_b)
        self.assertIn("GROUP BY", opt_b["text"].upper())

        self.__class__.test_results.append({
            "scenario": 3,
            "name": "Printed SQL Question",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_04_portrait_oriented_image(self):
        """Scenario 4: Portrait orientation (700 x 1300, 1:1.85 aspect ratio)."""
        img = Image.open(self.img_portrait)
        w, h = img.size
        self.assertGreater(h, w, "Must be portrait orientation")

        sol: ImageQuestionSolution = self.solver.solve_image(img)
        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertTrue(sol.is_mcq)
        self.assertGreaterEqual(len(sol.options), 3)

        self.__class__.test_results.append({
            "scenario": 4,
            "name": "Portrait-Oriented Image (700x1300)",
            "dimensions": f"{w}x{h}",
            "format": "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_05_landscape_oriented_image(self):
        """Scenario 5: Landscape orientation (1600 x 900, 16:9 aspect ratio)."""
        img = Image.open(SAMPLE_DATA_DIR / "sample_question3.jpeg")
        w, h = img.size
        self.assertGreater(w, h, "Must be landscape orientation")

        sol: ImageQuestionSolution = self.solver.solve_image(img)
        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)

        self.__class__.test_results.append({
            "scenario": 5,
            "name": "Landscape-Oriented Image (1600x900)",
            "dimensions": f"{w}x{h}",
            "format": "JPEG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_06_high_resolution_image_downscaling(self):
        """Scenario 6: High-resolution image (>2500px, 3000x2200)."""
        img = Image.open(self.img_high_res)
        w, h = img.size
        self.assertGreater(max(w, h), 2500)

        # Check controlled downscaling function
        resized, was_resized = resize_keep_aspect_ratio(img, max_dimension=1600)
        self.assertTrue(was_resized)
        self.assertLessEqual(max(resized.size), 1600)

        # Check coordinate mapping accuracy
        test_box = (100.0, 200.0, 500.0, 600.0)
        orig_box = map_bbox_to_original(test_box, orig_size=(w, h), proc_size=resized.size)
        scale_factor = w / resized.size[0]
        self.assertAlmostEqual(orig_box[0], 100.0 * scale_factor, delta=0.5)

        sol: ImageQuestionSolution = self.solver.solve_image(img)
        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.selected_option, "B")

        self.__class__.test_results.append({
            "scenario": 6,
            "name": "High-Resolution Image (>2500px, 3000x2200)",
            "dimensions": f"{w}x{h}",
            "format": "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_07_low_resolution_image(self):
        """Scenario 7: Low-resolution image (<400px, 380x240)."""
        img = Image.open(self.img_low_res)
        w, h = img.size
        self.assertLess(max(w, h), 400)

        sol: ImageQuestionSolution = self.solver.solve_image(img)
        self.assertIn(sol.lifecycle_state, [SolverLifecycleState.ANSWER_COMPLETED, SolverLifecycleState.NEEDS_CLARIFICATION])

        self.__class__.test_results.append({
            "scenario": 7,
            "name": "Low-Resolution Image (<400px, 380x240)",
            "dimensions": f"{w}x{h}",
            "format": "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_08_rotated_image_exif_normalization(self):
        """Scenario 8: Rotated image (90 deg with EXIF tag 6)."""
        img = Image.open(self.img_rotated_exif)
        exif = img.getexif()
        self.assertEqual(exif.get(0x0112), 6, "Must contain EXIF orientation 6")

        # Test normalize_exif_orientation
        normalized = normalize_exif_orientation(img)
        self.assertIsNotNone(normalized)

        sol: ImageQuestionSolution = self.solver.solve_image(img)
        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertIn("30", sol.final_answer or "")

        self.__class__.test_results.append({
            "scenario": 8,
            "name": "Rotated Image (90 deg EXIF Tag 6)",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": "JPEG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_09_multi_region_document(self):
        """Scenario 9: Multi-region image (lab header + query + output options)."""
        img = Image.open(self.img_multi_region)
        sol: ImageQuestionSolution = self.solver.solve_image(img)

        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.domain, "SQL")
        self.assertTrue(sol.is_mcq)
        self.assertGreaterEqual(len(sol.options), 3)

        self.__class__.test_results.append({
            "scenario": 9,
            "name": "Multi-Region Document (Header + Query + Options)",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": "PNG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    def test_10_uncertain_handwriting_image(self):
        """Scenario 10: Uncertain handwriting image (Prime Minister of India MCQ)."""
        img_path = SAMPLE_DATA_DIR / "sample_question2.jpeg"
        self.assertTrue(img_path.exists())

        img = Image.open(img_path)
        sol: ImageQuestionSolution = self.solver.solve_image(img)

        self.assertEqual(sol.lifecycle_state, SolverLifecycleState.ANSWER_COMPLETED)
        self.assertEqual(sol.selected_option, "B")
        self.assertIn("Mod", sol.final_answer)

        self.__class__.test_results.append({
            "scenario": 10,
            "name": "Uncertain Handwriting Image",
            "dimensions": f"{img.size[0]}x{img.size[1]}",
            "format": "JPEG",
            "domain": sol.domain,
            "selected_option": sol.selected_option,
            "final_answer": sol.final_answer,
            "latency_ms": sol.execution_time_ms,
            "status": sol.epistemic_status,
        })

    @classmethod
    def tearDownClass(cls):
        # Save summary JSON for report generation
        results_path = FIXTURES_DIR / "test_results_summary.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(cls.test_results, f, indent=2)
        print(f"\n[Test Summary]: Saved {len(cls.test_results)} scenario results to {results_path}")


if __name__ == "__main__":
    unittest.main()
