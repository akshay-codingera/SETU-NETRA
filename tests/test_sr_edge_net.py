"""
test_sr_edge_net.py: Formal test suite for SR-EdgeNet spatial-relational classifier.

Tests:
1. Model initialization and exact parameter count (~414k params).
2. Forward pass tensor shapes.
3. Training smoke test with FocalLoss and AdamW.
4. Checkpoint saving and loading.
5. End-to-end inference engine with predict_pair.
6. Invalid input handling and dimension validation.
7. Strict CPU compatibility.
"""

import sys
import unittest
from pathlib import Path
import numpy as np
import torch

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.structure.sr_edge_net import (
    SREdgeClassifier,
    SREdgeNetEngine,
    FocalLoss,
    SRClass,
    extract_pairwise_geometry
)


class TestSREdgeNet(unittest.TestCase):

    def setUp(self):
        self.device = torch.device("cpu")
        self.model = SREdgeClassifier(
            text_dim=384,
            text_proj_dim=64,
            spatial_dim=15,
            spatial_proj_dim=64,
            num_classes=4
        ).to(self.device)

    def test_01_model_initialization_and_params(self):
        """Test model initialization and verify parameter budget is ~414k."""
        params = self.model.parameter_count
        self.assertGreater(params, 380_000)
        self.assertLess(params, 450_000)
        self.assertEqual(params, 414_088)

    def test_02_forward_pass_shapes(self):
        """Test forward pass with batch size 8."""
        b_size = 8
        s_feats = torch.randn(b_size, 15, device=self.device)
        t_src = torch.randn(b_size, 384, device=self.device)
        t_tgt = torch.randn(b_size, 384, device=self.device)

        logits = self.model(s_feats, t_src, t_tgt)
        self.assertEqual(logits.shape, (b_size, 4))
        self.assertFalse(torch.isnan(logits).any())

    def test_03_training_smoke_test(self):
        """Test one optimization step using FocalLoss."""
        loss_fn = FocalLoss(gamma=2.0)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-3)

        s_feats = torch.randn(4, 15, device=self.device)
        t_src = torch.randn(4, 384, device=self.device)
        t_tgt = torch.randn(4, 384, device=self.device)
        targets = torch.tensor([0, 1, 2, 3], dtype=torch.long, device=self.device)

        self.model.train()
        optimizer.zero_grad()
        logits = self.model(s_feats, t_src, t_tgt)
        loss = loss_fn(logits, targets)
        loss.backward()

        # Check gradients
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.assertIsNotNone(param.grad, f"Gradient missing for {name}")

        optimizer.step()
        self.assertGreater(loss.item(), 0.0)

    def test_04_checkpoint_saving_and_loading(self):
        """Test saving and restoring model weights."""
        test_ckpt_path = "models/structure/test_checkpoint_temp.pt"
        torch.save({"model_state_dict": self.model.state_dict()}, test_ckpt_path)

        fresh_model = SREdgeClassifier().to(self.device)
        ckpt = torch.load(test_ckpt_path, map_location=self.device, weights_only=False)
        fresh_model.load_state_dict(ckpt["model_state_dict"])

        # Check numerical equality of weights
        for p1, p2 in zip(self.model.parameters(), fresh_model.parameters()):
            self.assertTrue(torch.equal(p1, p2))

        # Cleanup
        Path(test_ckpt_path).unlink(missing_ok=True)

    def test_05_inference_engine_predict_pair(self):
        """Test SREdgeNetEngine prediction interface."""
        engine = SREdgeNetEngine(checkpoint_path=None, device="cpu")
        engine.model = self.model

        s_geom = extract_pairwise_geometry(
            bbox_i=[60.0, 100.0, 500.0, 140.0],
            bbox_j=[60.0, 150.0, 300.0, 180.0],
            page_w=1200.0,
            page_h=1600.0
        )
        self.assertEqual(len(s_geom), 15)

        t_src_emb = np.random.randn(384).astype(np.float32)
        t_tgt_emb = np.random.randn(384).astype(np.float32)

        pred_label, conf, prob_dict = engine.predict_pair(s_geom, t_src_emb, t_tgt_emb)
        self.assertIn(pred_label, SRClass.CLASSES)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)
        self.assertAlmostEqual(sum(prob_dict.values()), 1.0, places=4)

    def test_06_invalid_input_handling(self):
        """Test dimension validation and error triggering."""
        # Spatial input with wrong dimensions (e.g., 10 instead of 15)
        wrong_s = torch.randn(2, 10, device=self.device)
        t_src = torch.randn(2, 384, device=self.device)
        t_tgt = torch.randn(2, 384, device=self.device)

        with self.assertRaises(Exception):
            self.model(wrong_s, t_src, t_tgt)

    def test_07_cpu_compatibility(self):
        """Assert all parameters and buffers reside strictly on CPU."""
        for p in self.model.parameters():
            self.assertEqual(p.device.type, "cpu")


if __name__ == "__main__":
    unittest.main()
