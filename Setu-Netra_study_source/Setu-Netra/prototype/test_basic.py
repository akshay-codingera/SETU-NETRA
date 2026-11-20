"""
Quick sanity tests for the v0 prototype. Not exhaustive — just enough to
confirm the pipeline behaves as expected before building on top of it.

Run: python3 -m unittest test_basic.py -v
"""

import unittest
from complexity_classifier import classify, EASY, MEDIUM, HARD
from router import route


class TestComplexityClassifier(unittest.TestCase):
    def test_easy_prompt(self):
        result = classify("What is the capital of France?")
        self.assertEqual(result.tier, EASY)

    def test_hard_prompt(self):
        result = classify(
            "Design a distributed cache eviction algorithm and prove its amortized time complexity."
        )
        self.assertEqual(result.tier, HARD)

    def test_medium_prompt(self):
        result = classify("Explain the difference between TCP and UDP.")
        self.assertEqual(result.tier, MEDIUM)


class TestRouter(unittest.TestCase):
    def test_easy_routes_to_small_model(self):
        decision = route("Define photosynthesis.")
        self.assertIn("small", decision.model.name.lower())

    def test_hard_routes_to_frontier_model(self):
        decision = route(
            "Derive the gradient of the cross-entropy loss function with respect to the logits."
        )
        self.assertIn("frontier", decision.model.name.lower())

    def test_cost_is_positive(self):
        decision = route("What is the capital of France?")
        self.assertGreater(decision.estimated_cost_usd, 0)


if __name__ == "__main__":
    unittest.main()
