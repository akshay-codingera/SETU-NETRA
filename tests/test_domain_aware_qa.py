"""
test_domain_aware_qa.py: Comprehensive test suite for Domain-Aware Solver Routing,
Safe AST Arithmetic Evaluation, Context-Aware OCR Normalization, and Epistemic Verification.
"""

import unittest
from pathlib import Path

from setu_netra.qa.domain_router import (
    DomainSolverRouter,
    EpistemicVerificationType,
    QuestionDomain,
    SafeArithmeticEvaluator,
    classify_domain,
    normalize_ocr_arithmetic_tokens,
)
from setu_netra.qa.engine import EvidenceGroundedQAEngine, VerifiedAnswer
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore


class SimpleDeterministicEngine(BaseEmbeddingEngine):
    """Deterministic embedding engine for unit tests."""

    def __init__(self, dimension: int = 32):
        self._dim = dimension

    @property
    def engine_name(self) -> str:
        return "deterministic-test-engine"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def embed_text(self, text: str):
        return [0.1] * self._dim

    def embed_texts(self, texts):
        return [[0.1] * self._dim for _ in texts]

    def embed_batch(self, texts):
        return [[0.1] * self._dim for _ in texts]


class TestDomainAwareQA(unittest.TestCase):
    """Test suite validating domain classification, safe math evaluation, and epistemic verification."""

    def test_01_mandatory_acceptance_tests(self):
        """Test the 5 mandatory acceptance expressions."""
        cases = [
            ("10 + 5 - 23 + 40", "32"),
            ("100 - 25 * 2", "50"),
            ("(100 - 25) * 2", "150"),
            ("-10 + 5", "-5"),
            ("20 / 4 + 3", "8"),
        ]
        for expr, expected in cases:
            res = DomainSolverRouter.solve_arithmetic_inquiry(expr)
            self.assertEqual(
                res.final_answer,
                expected,
                f"Expression '{expr}' failed: got {res.final_answer}, expected {expected}",
            )
            self.assertEqual(res.epistemic_status, EpistemicVerificationType.COMPUTATION_VERIFIED)
            self.assertEqual(res.domain, QuestionDomain.ARITHMETIC)
            self.assertEqual(res.verification_method, "DETERMINISTIC_AST_EVALUATION")
            self.assertEqual(res.citations, [])
            self.assertIn("Final Calculated Result", res.step_by_step_explanation)

    def test_02_decimal_numbers(self):
        """Test decimal floating-point arithmetic."""
        res = DomainSolverRouter.solve_arithmetic_inquiry("12.5 + 2.5 * 3")
        # 12.5 + 7.5 = 20
        self.assertEqual(res.final_answer, "20")
        self.assertEqual(res.epistemic_status, EpistemicVerificationType.COMPUTATION_VERIFIED)

    def test_03_ocr_uncertainty_and_normalization(self):
        """Test context-aware normalization on noisy OCR text (e.g. IO -> 10, 4O -> 40, Whot -> What)."""
        noisy_text = "a = IO ; b = 5 ; result = a+b - 23 + 4O ; Whot is the Value of result"
        norm, mutations = normalize_ocr_arithmetic_tokens(noisy_text)
        self.assertIn("10", norm)
        self.assertIn("40", norm)
        self.assertIn("what", norm.lower())
        self.assertGreaterEqual(len(mutations), 2)

        # Solve inquiry with OCR mutations
        res = DomainSolverRouter.solve_arithmetic_inquiry(noisy_text)
        self.assertEqual(res.final_answer, "32")
        self.assertEqual(res.epistemic_status, EpistemicVerificationType.COMPUTATION_VERIFIED)
        self.assertIn("result = 32", res.step_by_step_explanation)
        self.assertIn("Context-aware OCR glyph normalization applied", res.step_by_step_explanation)

    def test_04_safe_evaluator_security(self):
        """Ensure malicious expressions or forbidden AST nodes are strictly rejected."""
        dangerous_expressions = [
            "__import__('os').system('ls')",
            "eval('2+2')",
            "open('/etc/passwd').read()",
            "len([1, 2, 3])",
            "x.y + 1",
        ]
        for dangerous in dangerous_expressions:
            with self.assertRaises(ValueError):
                SafeArithmeticEvaluator.evaluate(dangerous)

    def test_05_division_by_zero(self):
        """Ensure division by zero raises ZeroDivisionError rather than crashing."""
        with self.assertRaises(ZeroDivisionError):
            SafeArithmeticEvaluator.evaluate("10 / 0")

    def test_06_domain_classification(self):
        """Verify robust domain classification across all six domains."""
        # 1. ARITHMETIC
        d1, _, _ = classify_domain("calculate 10 + 5 - 23 + 40")
        self.assertEqual(d1, QuestionDomain.ARITHMETIC)

        d1_vars, _, _ = classify_domain("a = 10; b = 5; result = a + b; what is value of result?")
        self.assertEqual(d1_vars, QuestionDomain.ARITHMETIC)

        # 2. SQL
        d2, _, _ = classify_domain("SELECT department, COUNT(*) FROM employees GROUP BY department")
        self.assertEqual(d2, QuestionDomain.SQL)

        # 3. MATHEMATICS
        d3, _, _ = classify_domain("What is the time complexity of performing 2D convolution with HxW and KxK?")
        self.assertEqual(d3, QuestionDomain.MATHEMATICS)

        # 4. PROGRAMMING
        d4, _, _ = classify_domain("def compute_hash(data): return hashlib.sha256(data).hexdigest()")
        self.assertEqual(d4, QuestionDomain.PROGRAMMING)

        # 5. GENERAL_KNOWLEDGE
        d5, _, _ = classify_domain("Who was the prime minister of India in 2020?")
        self.assertEqual(d5, QuestionDomain.GENERAL_KNOWLEDGE)

        # 6. DOCUMENT_QA
        d6, _, _ = classify_domain("What are the architectural invariants of the EventBus in SETU-NETRA?")
        self.assertEqual(d6, QuestionDomain.DOCUMENT_QA)

    def test_07_engine_arithmetic_routing(self):
        """Verify EvidenceGroundedQAEngine routes arithmetic queries directly to safe solver."""
        store = SQLiteDocumentStore(db_path=":memory:")
        embedding_engine = SimpleDeterministicEngine()
        retriever = DocumentRetriever(store=store, embedding_engine=embedding_engine)
        engine = EvidenceGroundedQAEngine(retriever=retriever)

        answer: VerifiedAnswer = engine.answer_question(
            query="10 + 5 - 23 + 40",
            workspace_id="default",
        )
        self.assertEqual(answer.answer_text, "32")
        self.assertEqual(answer.epistemic_status, "COMPUTATION_VERIFIED")
        self.assertEqual(answer.domain, "ARITHMETIC")
        self.assertEqual(answer.verification_method, "DETERMINISTIC_AST_EVALUATION")
        self.assertEqual(answer.citations, [])
        self.assertEqual(answer.grounding_score, 1.0)
        self.assertIn("result = 32", answer.explanation)


if __name__ == "__main__":
    unittest.main()
