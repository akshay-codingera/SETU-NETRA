"""
test_semantic.py: Comprehensive unit test suite for Module 4 Semantic Understanding.

Covers all 24 required scenarios strictly offline without downloading neural weights:
    python -m unittest tests/test_semantic.py
"""

import json
import sys
import unittest
from pathlib import Path

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import (
    BlockType,
    DocumentBlock,
    DocumentStructureResult,
    QuestionGroup,
    QuestionIntent,
    QuestionOption,
    SemanticAnalysisResult,
    SemanticItemAnalysis,
    TechnicalLevel,
)
from setu_netra.semantic.domain.classifier import OpenVocabularyDomainClassifier
from setu_netra.semantic.domain.disambiguation import disambiguate_terms
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.semantic.engine import SemanticUnderstandingEngine


class TestSemanticUnderstanding(unittest.TestCase):
    """Test suite covering the 24 required semantic understanding scenarios."""

    def setUp(self):
        self.offline_engine = OfflineSemanticEngine(dimension=512)
        self.engine = SemanticUnderstandingEngine(embedding_engine=self.offline_engine)

    # 1. A basic definition question
    def test_01_basic_definition_question(self):
        query = "What is meant by the definition of an algorithm in computer science?"
        res = self.engine.analyze_text(query, source_id="q1")
        self.assertIn(QuestionIntent.DEFINITION, res.question_intents)
        self.assertEqual(res.primary_domain, "Algorithms & Computational Complexity")
        self.assertEqual(res.status, "ANALYZED")

    # 2. A question phrased in everyday language
    def test_02_everyday_language_phrasing(self):
        query = "How long does this sorting procedure take to finish running on a laptop?"
        res = self.engine.analyze_text(query, source_id="q2")
        self.assertIn(QuestionIntent.COMPLEXITY_ANALYSIS, res.question_intents)
        self.assertEqual(res.primary_domain, "Algorithms & Computational Complexity")

    # 3. An advanced technical question
    def test_03_advanced_technical_question(self):
        query = "Derive the asymptotic worst-case running-time bound for 2D convolution."
        res = self.engine.analyze_text(query, source_id="q3")
        self.assertEqual(res.technical_level, TechnicalLevel.ADVANCED)
        self.assertIn(QuestionIntent.DERIVATION, res.question_intents)

    # 4. A paraphrase with different vocabulary
    def test_04_paraphrase_different_vocabulary(self):
        q_canonical = "What is the computational complexity of the algorithm?"
        q_paraphrase = "Estimate the computational cost and time complexity of the procedure."
        sim = self.offline_engine.similarity(q_canonical, q_paraphrase)
        self.assertGreater(sim, 0.40)
        res = self.engine.analyze_text(q_paraphrase)
        self.assertEqual(res.primary_domain, "Algorithms & Computational Complexity")

    # 5. Two related but semantically distinct questions
    def test_05_two_related_distinct_questions(self):
        q1 = "How do you encrypt a message with an AES secret key?"
        q2 = "How do you hash a message with a SHA-256 digest?"
        res1 = self.engine.analyze_text(q1)
        res2 = self.engine.analyze_text(q2)
        self.assertTrue(any(c.normalized_form == "Data Encryption" for c in res1.concepts))
        self.assertTrue(any(c.normalized_form == "Cryptographic Hashing" for c in res2.concepts))

    # 6. Time complexity versus space complexity
    def test_06_time_vs_space_complexity(self):
        q_time = "What is the time complexity of the merge sort algorithm?"
        q_space = "What is the auxiliary space complexity of the merge sort algorithm?"
        res_time = self.engine.analyze_text(q_time)
        res_space = self.engine.analyze_text(q_space)
        time_concepts = [c.normalized_form for c in res_time.concepts]
        space_concepts = [c.normalized_form for c in res_space.concepts]
        self.assertIn("Time Complexity", time_concepts)
        self.assertIn("Space Complexity", space_concepts)
        self.assertNotIn("Space Complexity", time_concepts)

    # 7. Contextual disambiguation of a word such as 'kernel'
    def test_07_contextual_disambiguation_kernel(self):
        text_os = "The Linux operating system kernel manages processes and CPU scheduling."
        text_img = "Apply a 3x3 convolution filter kernel to the image pixels for edge detection."
        disambig_os = disambiguate_terms(text_os)[0]
        disambig_img = disambiguate_terms(text_img)[0]
        self.assertIn("Operating Systems", disambig_os.resolved_sense)
        self.assertIn("Image Processing", disambig_img.resolved_sense)

    # 8. A question involving multiple domains
    def test_08_multi_domain_question(self):
        query = "What is the computational complexity of performing 2D convolution on an image?"
        res = self.engine.analyze_text(query)
        dom_names = [d.domain_name for d in res.domains]
        self.assertIn("Signal & Digital Image Processing", dom_names)

    # 9. A previously unseen phrase expressing a familiar concept
    def test_09_unseen_phrase_familiar_concept(self):
        query = "Determine the asymptotic bound on the number of elementary operations executed."
        res = self.engine.analyze_text(query)
        self.assertEqual(res.primary_domain, "Algorithms & Computational Complexity")

    # 10. An unsupported or unknown domain
    def test_10_unsupported_unknown_domain(self):
        query = "Calculate the relativistic frame-dragging magnetosphere precession of a Kerr black hole."
        res = self.engine.analyze_text(query)
        self.assertIn(res.status, ("UNKNOWN_DOMAIN", "INSUFFICIENT_EVIDENCE"))

    # 11. A non-question paragraph
    def test_11_non_question_paragraph(self):
        para = "Optical Character Recognition translates raster image pixels into alphanumeric characters."
        res = self.engine.analyze_text(para, source_id="block-para")
        self.assertIn(QuestionIntent.UNKNOWN, res.question_intents)
        self.assertEqual(res.source_id, "block-para")

    # 12. A question with multiple intents
    def test_12_multiple_intents(self):
        query = "Explain why the algorithm has logarithmic time complexity and calculate the steps for N=1024."
        res = self.engine.analyze_text(query)
        self.assertIn(QuestionIntent.EXPLANATION, res.question_intents)
        self.assertIn(QuestionIntent.CALCULATION, res.question_intents)
        self.assertIn(QuestionIntent.COMPLEXITY_ANALYSIS, res.question_intents)

    # 13. Mathematical notation and quantities
    def test_13_mathematical_notation_and_quantities(self):
        query = "Given an image of size H x W and a kernel of size K x K, the complexity is O(H * W * K^2)."
        res = self.engine.analyze_text(query)
        ent_types = [e.entity_type for e in res.entities]
        self.assertIn("BIG_O_NOTATION", ent_types)
        self.assertIn("GRID_DIMENSION", ent_types)

    # 14. Missing optional input fields
    def test_14_missing_optional_fields(self):
        res = self.engine.analyze_text("What is TCP?", context_text="")
        self.assertIsNotNone(res.source_id)
        self.assertEqual(res.status, "ANALYZED")

    # 15. Empty or malformed input
    def test_15_empty_or_malformed_input(self):
        res = self.engine.analyze_text("   ")
        self.assertEqual(res.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(len(res.domains), 0)

    # 16. OCR-corrupted text
    def test_16_ocr_corrupted_text(self):
        corrupted = "What e the computationa complexit of performing convolution onan imaqe ofsize HxWwitha kernelofsize KxK?"
        res = self.engine.analyze_text(corrupted)
        self.assertEqual(res.primary_domain, "Signal & Digital Image Processing")
        self.assertTrue(any(c.normalized_form == "Computational Complexity" for c in res.concepts))

    # 17. Uncertainty and abstention
    def test_17_uncertainty_and_abstention(self):
        gibberish = "qwjkle rtyui opasdf ghjkl zxcvbnm"
        res = self.engine.analyze_text(gibberish)
        self.assertIn(res.status, ("UNKNOWN_DOMAIN", "INSUFFICIENT_EVIDENCE"))
        self.assertGreater(len(res.warnings), 0)

    # 18. Preservation of original text
    def test_18_preservation_of_original_text(self):
        raw = "What e the computationa complexit?"
        res = self.engine.analyze_text(raw)
        self.assertEqual(res.original_text, raw)

    # 19. Preservation of source identifiers
    def test_19_preservation_of_source_identifiers(self):
        res = self.engine.analyze_text("Define an algorithm.", source_id="question-block-42")
        self.assertEqual(res.source_id, "question-block-42")

    # 20. Offline operation without model downloads
    def test_20_offline_operation_without_downloads(self):
        engine = get_embedding_engine("offline")
        self.assertEqual(engine.engine_name, "offline_semantic_tfidf")
        vec = engine.embed_texts(["Offline semantic verification."])
        self.assertEqual(vec.shape, (1, 512))

    # 21. Optional model-unavailable behavior
    def test_21_model_unavailable_behavior(self):
        neural = NeuralSentenceEmbeddingEngine("non_existent_local_model_xyz")
        self.assertFalse(neural.is_available())
        with self.assertRaises(RuntimeError):
            neural.embed_texts(["Test"])

    # 22. JSON serialization
    def test_22_json_serialization(self):
        res = self.engine.analyze_text("What is 2D convolution?")
        serialized = json.dumps({
            "source_id": res.source_id,
            "domain": res.primary_domain,
            "intents": list(res.question_intents),
        })
        self.assertIn("Signal & Digital Image Processing", serialized)

    # 23. Multiple questions without mixing their evidence
    def test_23_multiple_questions_without_mixing(self):
        q1 = QuestionGroup(question_block_id=1, question_text="Who is the Prime Minister of India?")
        q2 = QuestionGroup(question_block_id=2, question_text="What is the time complexity of 2D convolution?")
        struct_res = DocumentStructureResult(blocks=[], questions=[q1, q2])
        doc_res = self.engine.analyze_document_structure(struct_res)
        self.assertEqual(len(doc_res.items), 2)
        self.assertEqual(doc_res.items[0].primary_domain, "Political Science, Civics & Governance")
        self.assertIn(doc_res.items[1].primary_domain, ("Signal & Digital Image Processing", "Algorithms & Computational Complexity"))

    # 24. Repeated inputs and model reuse where applicable
    def test_24_repeated_inputs_and_model_reuse(self):
        query = "What is the time complexity of 2D convolution?"
        res_a = self.engine.analyze_text(query)
        res_b = self.engine.analyze_text(query)
        self.assertEqual(res_a.primary_domain, res_b.primary_domain)
        self.assertEqual(res_a.domains[0].similarity_score, res_b.domains[0].similarity_score)


class TestSemanticBackendUpgrades(unittest.TestCase):
    """Integration and unit tests for pretrained neural embeddings and backend selection."""

    def test_01_offline_backend_standalone(self):
        """Verify offline engine produces strictly 512-dim vectors without neural model."""
        off = OfflineSemanticEngine(dimension=512)
        self.assertEqual(off.engine_name, "offline_semantic_tfidf")
        self.assertEqual(off.dimension, 512)
        vecs = off.embed_texts(["Algorithms and computational asymptotic runtime."])
        self.assertEqual(vecs.shape, (1, 512))
        norm = float((vecs[0] ** 2).sum() ** 0.5)
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_02_neural_backend_loads_real_weights(self):
        """Verify NeuralSentenceEmbeddingEngine loads genuine 384-dim weights."""
        neural = NeuralSentenceEmbeddingEngine("all-MiniLM-L6-v2")
        self.assertTrue(neural.is_available())
        self.assertEqual(neural.dimension, 384)
        self.assertEqual(neural.engine_name, "neural_all-MiniLM-L6-v2")
        meta = neural.model_metadata
        self.assertEqual(meta["embedding_dimension"], 384)
        self.assertEqual(meta["license"], "Apache-2.0")
        
        vecs = neural.embed_texts(["2D convolution spatial filtering."])
        self.assertEqual(vecs.shape, (1, 384))
        norm = float((vecs[0] ** 2).sum() ** 0.5)
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_03_neural_backend_fails_clearly_when_weights_unavailable(self):
        """Verify neural backend raises informative RuntimeError on non-existent model."""
        bad_neural = NeuralSentenceEmbeddingEngine("non_existent_model_12345")
        self.assertFalse(bad_neural.is_available())
        with self.assertRaises(RuntimeError) as ctx:
            bad_neural.embed_texts(["Test text"])
        self.assertIn("not locally available", str(ctx.exception))
        self.assertIn("download_semantic_model.py", str(ctx.exception))

    def test_04_factory_explicit_selection_and_auto_reporting(self):
        """Verify factory supports offline, neural, and auto reporting."""
        off = get_embedding_engine("offline")
        self.assertEqual(off.engine_name, "offline_semantic_tfidf")

        neu = get_embedding_engine("neural")
        self.assertIn("all-MiniLM-L6-v2", neu.engine_name)

        auto = get_embedding_engine("auto")
        # In this environment weights are cached, so auto selects neural
        self.assertIn("neural", auto.engine_name)

        # Invalid engine name raises ValueError
        with self.assertRaises(ValueError):
            get_embedding_engine("unsupported_backend_xyz")

    def test_05_no_dimension_manipulation_or_padding(self):
        """Verify classifier uses native dimensions without padding or truncating."""
        off = OfflineSemanticEngine()
        neu = NeuralSentenceEmbeddingEngine()
        
        clf_off = OpenVocabularyDomainClassifier(embedding_engine=off)
        clf_neu = OpenVocabularyDomainClassifier(embedding_engine=neu)

        self.assertEqual(clf_off.cached_vectors_shape[1], 512)
        self.assertEqual(clf_neu.cached_vectors_shape[1], 384)

    def test_06_domain_vectors_cache_and_invalidation(self):
        """Verify domain description embeddings are cached and invalidated when engine changes."""
        off = OfflineSemanticEngine()
        neu = NeuralSentenceEmbeddingEngine()

        clf = OpenVocabularyDomainClassifier(embedding_engine=off)
        self.assertEqual(clf.cached_vectors_shape[1], 512)
        old_cache = clf._cached_domain_vectors

        # Switch engine to neural
        clf.set_embedding_engine(neu)
        self.assertEqual(clf.cached_vectors_shape[1], 384)
        self.assertNotEqual(clf._cached_domain_vectors.shape, old_cache.shape)

    def test_07_empty_and_batch_inputs(self):
        """Verify empty and batch embedding inputs for both backends."""
        off = OfflineSemanticEngine()
        neu = NeuralSentenceEmbeddingEngine()

        for eng in (off, neu):
            empty_vecs = eng.embed_texts([])
            self.assertEqual(empty_vecs.shape, (0, eng.dimension))

            batch_vecs = eng.embed_texts(["First query", "Second query", "Third query"])
            self.assertEqual(batch_vecs.shape, (3, eng.dimension))

    def test_08_neural_unknown_domain_abstention(self):
        """Verify neural backend abstains on unrelated everyday query."""
        neu_engine = SemanticUnderstandingEngine(embedding_engine=get_embedding_engine("neural"))
        res = neu_engine.analyze_text("What is the best recipe and oven temperature for baking chocolate chip cookies?")
        self.assertEqual(res.status, "UNKNOWN_DOMAIN")
        self.assertGreater(len(res.warnings), 0)

    def test_09_neural_paraphrase_matching(self):
        """Verify neural backend matches conversational question to Algorithms."""
        neu_engine = SemanticUnderstandingEngine(embedding_engine=get_embedding_engine("neural"))
        res = neu_engine.analyze_text("How long does this sorting procedure take to finish running on a laptop?")
        self.assertEqual(res.primary_domain, "Algorithms & Computational Complexity")
        self.assertEqual(res.status, "ANALYZED")

    def test_10_provenance_and_immutability_under_neural(self):
        """Verify source ID and text are preserved under neural analysis."""
        neu_engine = SemanticUnderstandingEngine(embedding_engine=get_embedding_engine("neural"))
        raw = "What is the time complexity of merge sort?"
        res = neu_engine.analyze_text(raw, source_id="q-unique-789")
        self.assertEqual(res.source_id, "q-unique-789")
        self.assertEqual(res.original_text, raw)


if __name__ == "__main__":
    unittest.main()
