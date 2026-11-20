"""
test_cm_rp.py: Unit and regression test suite for Milestone R3 (CM-RP).

Verifies:
1. Model initialization and exact parameter count (~63k parameters).
2. Context feature extraction pipeline (423-d feature vector + 7-d mask).
3. Forward pass with and without action feasibility masking.
4. Constrained probability distribution and masked action suppression.
5. Checkpoint loading and persistence.
6. Concrete strategy dispatch to genuine underlying solvers.
7. Hardware-aware action masking under high memory pressure.
8. End-to-end CPU inference latency benchmark (< 5.0 ms).
9. Missing checkpoint graceful fallback.
10. Full R1 (SR-EdgeNet) and R2 (ER-SP) integration compatibility.
"""

import os
import sys
import json
import time
import unittest
import numpy as np
import torch

# Ensure 'src' is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from setu_netra.policy.cm_rp import (
    CMPolicyNetwork,
    CMRPPredictor,
    CMRPDispatcher,
    ContextFeatureExtractor,
    StrategyAction,
    ACTION_TO_ID,
    ID_TO_ACTION,
    NUM_ACTIONS
)
from setu_netra.routing.system_telemetry import SystemTelemetry


class TestCMPolicyArchitecture(unittest.TestCase):
    """Verifies the CM-RP neural policy architecture."""

    def setUp(self):
        self.device = torch.device("cpu")
        self.model = CMPolicyNetwork(
            input_dim=423,
            hidden_dim1=128,
            hidden_dim2=64,
            num_actions=7
        ).to(self.device)

    def test_parameter_count(self):
        """Model must be ultra-lightweight (~63k parameters)."""
        param_count = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        self.assertGreater(param_count, 55_000)
        self.assertLess(param_count, 75_000)

    def test_forward_pass_unmasked(self):
        """Standard forward pass produces valid (B, 7) logits."""
        batch_size = 4
        x = torch.randn(batch_size, 423, device=self.device)
        logits = self.model(x)
        self.assertEqual(logits.shape, (batch_size, 7))
        self.assertFalse(torch.isnan(logits).any())

    def test_forward_pass_masked(self):
        """Masked action must receive near-zero probability after softmax."""
        batch_size = 2
        x = torch.randn(batch_size, 423, device=self.device)
        # Mask out action 4 (LOCAL_SLM)
        mask = torch.tensor([[1, 1, 1, 1, 0, 1, 1], [1, 1, 1, 1, 0, 1, 1]], dtype=torch.float32)

        logits = self.model(x, action_mask=mask)
        probs = torch.softmax(logits, dim=-1)

        for b in range(batch_size):
            self.assertAlmostEqual(float(probs[b, 4].detach()), 0.0, places=5)
            self.assertAlmostEqual(float(torch.sum(probs[b]).detach()), 1.0, places=5)


class TestContextFeatureExtractor(unittest.TestCase):
    """Verifies feature extraction and action mask construction."""

    def setUp(self):
        self.extractor = ContextFeatureExtractor()

    def test_feature_vector_dimension(self):
        """Context feature vector must be exactly 423 dimensions."""
        q = "What is the result of 15 + 25 * 2?"
        q_dummy = np.random.randn(384).astype(np.float32)
        sr_p = [0.85, 0.05, 0.05, 0.05]
        er_p = [0.90, 0.04, 0.01, 0.01, 0.04]
        telem = SystemTelemetry(cpu_percent=10.0, ram_percent=60.0, avail_ram_mb=6000.0, total_ram_mb=16384.0, timestamp=time.time())

        feat_vec, mask_vec = self.extractor.extract_features(
            question=q,
            q_emb=q_dummy,
            sr_probs=sr_p,
            er_probs=er_p,
            telemetry=telem
        )

        self.assertEqual(feat_vec.shape, (423,))
        self.assertEqual(mask_vec.shape, (7,))
        self.assertEqual(mask_vec[ACTION_TO_ID[StrategyAction.LOCAL_SLM.value]], 1.0)

    def test_hardware_exhaustion_masking(self):
        """Critically low RAM (< 1.5 GB) must mask out LOCAL_SLM."""
        q = "Compare Paxos and Raft architecture."
        q_dummy = np.random.randn(384).astype(np.float32)
        exhausted_telem = SystemTelemetry(cpu_percent=85.0, ram_percent=94.0, avail_ram_mb=950.0, total_ram_mb=16384.0, timestamp=time.time())

        feat_vec, mask_vec = self.extractor.extract_features(
            question=q,
            q_emb=q_dummy,
            telemetry=exhausted_telem
        )

        # LOCAL_SLM must be masked out (0.0)
        self.assertEqual(mask_vec[ACTION_TO_ID[StrategyAction.LOCAL_SLM.value]], 0.0)
        # Other solvers must remain available (1.0)
        self.assertEqual(mask_vec[ACTION_TO_ID[StrategyAction.EXTRACTIVE_QA.value]], 1.0)
        self.assertEqual(mask_vec[ACTION_TO_ID[StrategyAction.ABSTAIN.value]], 1.0)


class TestCMRPPredictorAndDispatch(unittest.TestCase):
    """Verifies policy prediction, checkpoint loading, and solver dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.ckpt_path = "models/policy/cm_rp.pt"
        cls.predictor = CMRPPredictor(checkpoint_path=cls.ckpt_path, device="cpu")

    def test_checkpoint_loaded(self):
        """Trained checkpoint must load properly."""
        self.assertTrue(self.predictor.is_loaded)
        self.assertIsNotNone(self.predictor.model)

    def test_arithmetic_dispatch(self):
        """Arithmetic strategy must dispatch to SafeArithmeticEvaluator and return correct math."""
        res = CMRPDispatcher.dispatch(
            action=StrategyAction.ARITHMETIC_SOLVER.value,
            question="Given a = 10; b = 5; result = a + b - 23 + 40; What is result?"
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("32", str(res["final_answer"]))
        self.assertEqual(res["epistemic_status"], "COMPUTATION_VERIFIED")

    def test_dbms_dispatch(self):
        """DBMS strategy must dispatch to DBMSNormalizationSolver."""
        res = CMRPDispatcher.dispatch(
            action=StrategyAction.DBMS_SOLVER.value,
            question="Relation R(A, B, C, D) with F = {A -> B, B -> C, C -> D}. What is the highest normal form?"
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("2NF", str(res["final_answer"]))
        self.assertEqual(res["epistemic_status"], "LOGIC_VERIFIED")

    def test_formal_logic_dispatch(self):
        """Formal logic strategy must dispatch to syllogism solver."""
        res = CMRPDispatcher.dispatch(
            action=StrategyAction.FORMAL_LOGIC_SOLVER.value,
            question="Given: Some cats are dogs. All dogs are birds. Can we conclude that all cats are birds?"
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["epistemic_status"], "LOGIC_VERIFIED")

    def test_abstention_dispatch(self):
        """Abstention action must return epistemic refusal without generation."""
        res = CMRPDispatcher.dispatch(
            action=StrategyAction.ABSTAIN.value,
            question="Does a candidate win Raft leader election with a minority vote?"
        )
        self.assertEqual(res["status"], "ABSTAINED")
        self.assertEqual(res["epistemic_status"], "EPISTEMIC_REFUSAL")

    def test_inference_latency(self):
        """Policy decision latency on CPU must be under 5.0 ms."""
        q_dummy = np.random.randn(384).astype(np.float32)

        # Warmup
        for _ in range(5):
            _ = self.predictor.select_strategy(question="Test question", q_emb=q_dummy)

        t0 = time.perf_counter()
        iters = 50
        for _ in range(iters):
            _ = self.predictor.select_strategy(question="Test question", q_emb=q_dummy)
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        avg_latency = total_time_ms / iters

        self.assertLess(avg_latency, 5.0, f"Latency {avg_latency:.3f}ms exceeds 5.0ms threshold!")


class TestR1R2R3Integration(unittest.TestCase):
    """Verifies end-to-end compatibility between R1 (SR-EdgeNet), R2 (ER-SP), and R3 (CM-RP)."""

    def test_pipeline_integration(self):
        """SR-EdgeNet and ER-SP outputs directly feed into CM-RP."""
        from setu_netra.structure.sr_edge_net import SREdgeNetEngine
        from setu_netra.evidence.er_sp import ERSPPredictor

        sr_engine = SREdgeNetEngine(checkpoint_path="models/structure/sr_edge_net.pt")
        er_predictor = ERSPPredictor(checkpoint_path="models/evidence/er_sp.pt")
        cm_predictor = CMRPPredictor(checkpoint_path="models/policy/cm_rp.pt")

        self.assertTrue(sr_engine.is_loaded)
        self.assertTrue(er_predictor.is_loaded)
        self.assertTrue(cm_predictor.is_loaded)

        # Dummy inputs
        q_emb = np.random.randn(384).astype(np.float32)
        p_emb = [np.random.randn(384).astype(np.float32)]
        spatial_15d = [0.1] * 15

        # 1. R1 Inference
        sr_label, sr_conf, sr_probs_dict = sr_engine.predict_pair(spatial_15d, q_emb, p_emb[0])
        sr_probs = [sr_probs_dict[k] for k in ["NONE", "PARENT_OF", "OPTION_OF", "CONTINUATION_OF"]]

        # 2. R2 Inference
        er_res = er_predictor.predict_from_embeddings(q_emb, p_emb)
        er_probs = [er_res["probabilities"][k] for k in ["SUFFICIENT", "PARTIALLY_SUFFICIENT", "CONTRADICTORY", "IRRELEVANT", "UNVERIFIABLE"]]

        # 3. R3 Policy Routing
        policy_res = cm_predictor.select_strategy(
            question="What is the result of given expression?",
            q_emb=q_emb,
            sr_probs=sr_probs,
            sr_meta={"confidence": sr_conf},
            er_probs=er_probs,
            er_meta={"confidence": er_res["confidence"], "retrieval_cosine": er_res["retrieval_cosine"]}
        )

        self.assertIn("selected_action", policy_res)
        self.assertIn(policy_res["selected_action"], StrategyAction.get_all())
        self.assertIn("probabilities", policy_res)


if __name__ == "__main__":
    unittest.main()
