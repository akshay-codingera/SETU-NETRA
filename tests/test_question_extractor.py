"""
test_question_extractor.py: Unit tests for question segmentation, option parsing,
and intent classification in SETU-NETRA Stage 3.

Tests:
1. Cognitive intent classification (DEFINITION, COMPARISON, CALCULATION, MECHANISM, MCQ_SELECTION, OPEN_ENDED).
2. Single question extraction from raw text.
3. Multi-question segmentation.
4. MCQ extraction and option label parsing ((A), (B), (C), (D) or 1., 2., 3., 4.).
5. Extraction from DocumentStructureResult and QuestionGroup.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import DocumentBlock, DocumentStructureResult, QuestionGroup, QuestionOption
from setu_netra.qa.question_extractor import QuestionExtractor, classify_question_intent


class TestQuestionExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = QuestionExtractor()

    def test_classify_question_intent(self):
        self.assertEqual(classify_question_intent("What is a page fault?", is_mcq=False), "DEFINITION")
        self.assertEqual(classify_question_intent("Define virtual memory.", is_mcq=False), "DEFINITION")
        self.assertEqual(classify_question_intent("Compare TCP and UDP protocols.", is_mcq=False), "COMPARISON")
        self.assertEqual(classify_question_intent("What is the difference between processes and threads?", is_mcq=False), "COMPARISON")
        self.assertEqual(classify_question_intent("Calculate the average memory access time.", is_mcq=False), "CALCULATION")
        self.assertEqual(classify_question_intent("Compute the Hamming distance between code words.", is_mcq=False), "CALCULATION")
        self.assertEqual(classify_question_intent("Explain how the two-phase locking protocol prevents deadlocks.", is_mcq=False), "MECHANISM")
        self.assertEqual(classify_question_intent("How does DNS resolution operate across recursive resolvers?", is_mcq=False), "MECHANISM")
        self.assertEqual(classify_question_intent("Which protocol operates at Layer 4?", is_mcq=True), "MCQ_SELECTION")
        self.assertEqual(classify_question_intent("Consider future challenges in distributed consensus.", is_mcq=False), "OPEN_ENDED")

    def test_extract_single_question_from_text(self):
        text = "What is the primary function of the transport layer in the OSI model?"
        questions = self.extractor.extract_from_raw_text(text)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q.prompt, text)
        self.assertFalse(q.is_mcq)
        self.assertEqual(q.intent, "DEFINITION")
        self.assertEqual(len(q.options), 0)

    def test_extract_multiple_questions_from_text(self):
        text = (
            "Q1. Define cache coherence.\n\n"
            "Q2. Explain the difference between write-through and write-back caches.\n\n"
            "Q3. Calculate the cache miss penalty if hit time is 1ns and miss rate is 5%."
        )
        questions = self.extractor.extract_from_raw_text(text)
        self.assertEqual(len(questions), 3)

        self.assertIn("Define cache coherence", questions[0].prompt)
        self.assertEqual(questions[0].intent, "DEFINITION")

        self.assertIn("difference between write-through and write-back", questions[1].prompt)
        self.assertEqual(questions[1].intent, "COMPARISON")

        self.assertIn("Calculate the cache miss penalty", questions[2].prompt)
        self.assertEqual(questions[2].intent, "CALCULATION")

    def test_extract_mcq_with_options(self):
        text = (
            "Question 1: Which data structure is utilized for Breadth-First Search (BFS)?\n"
            "(A) Stack\n"
            "(B) Queue\n"
            "(C) Priority Queue\n"
            "(D) Hash Table"
        )
        questions = self.extractor.extract_from_raw_text(text)
        self.assertEqual(len(questions), 1)

        mcq = questions[0]
        self.assertTrue(mcq.is_mcq)
        self.assertEqual(mcq.intent, "MCQ_SELECTION")
        self.assertEqual(len(mcq.options), 4)

        expected_labels = ["A", "B", "C", "D"]
        for opt, exp_label in zip(mcq.options, expected_labels):
            self.assertEqual(opt["label"], exp_label)
        self.assertEqual(mcq.options[1]["text"], "Queue")

    def test_extract_from_structure_with_question_groups(self):
        q_grp = QuestionGroup(
            question_block_id=1,
            question_text="Which of the following sorting algorithms has O(n log n) worst-case time?",
            question_number=1,
            options=[
                QuestionOption(option_label="A", option_text="Quicksort", block_id=2, confidence=0.99, bbox=(50, 80, 200, 100)),
                QuestionOption(option_label="B", option_text="Merge Sort", block_id=3, confidence=0.99, bbox=(50, 110, 200, 130)),
                QuestionOption(option_label="C", option_text="Bubble Sort", block_id=4, confidence=0.99, bbox=(50, 140, 200, 160)),
            ],
            bbox=(50, 50, 600, 160),
            warnings=[],
        )
        struct_res = DocumentStructureResult(
            blocks=[],
            questions=[q_grp],
            raw_transcript="",
            reading_order_box_indices=[],
            processing_time_ms=5.0,
            status="SUCCESS",
            warnings=[],
            metadata={},
        )

        questions = self.extractor.extract_from_structure(struct_res, page_num=2)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertTrue(q.is_mcq)
        self.assertEqual(q.intent, "MCQ_SELECTION")
        self.assertEqual(len(q.options), 3)
        self.assertEqual(q.page_number, 2)


if __name__ == "__main__":
    unittest.main()
