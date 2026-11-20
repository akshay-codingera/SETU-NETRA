"""
sr_edge_net.py: Spatial-Relational Edge Network (SR-EdgeNet) for SETU-NETRA.

Architecture:
- Frozen MiniLM (384-d) dense semantic representations for node texts.
- 15-dimensional normalized relative spatial feature vectors for candidate directed edges.
- Trainable dual-branch projection & deep pairwise fusion MLP (~414k parameters).
- Four-class classification taxonomy:
    0: PARENT_OF
    1: OPTION_OF
    2: CONTINUATION_OF
    3: NONE
"""

import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from setu_netra.core.contracts import DocumentBlock, OCRBox


# Target Relationship Classes
class SRClass:
    PARENT_OF = "PARENT_OF"
    OPTION_OF = "OPTION_OF"
    CONTINUATION_OF = "CONTINUATION_OF"
    NONE = "NONE"

    CLASSES = [PARENT_OF, OPTION_OF, CONTINUATION_OF, NONE]
    ID_TO_LABEL = {0: PARENT_OF, 1: OPTION_OF, 2: CONTINUATION_OF, 3: NONE}
    LABEL_TO_ID = {PARENT_OF: 0, OPTION_OF: 1, CONTINUATION_OF: 2, NONE: 3}


class FocalLoss(nn.Module):
    """Multi-class Focal Loss for handling severe class imbalance."""

    def __init__(
        self,
        gamma: float = 2.0,
        weight: Optional[torch.Tensor] = None,
        reduction: str = "mean"
    ):
        super().__init__()
        self.gamma = gamma
        self.weight = weight
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.weight)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss


class SREdgeClassifier(nn.Module):
    """Pairwise Spatial-Relational Neural Classifier (~414k parameters)."""

    def __init__(
        self,
        text_dim: int = 384,
        text_proj_dim: int = 64,
        spatial_dim: int = 15,
        spatial_proj_dim: int = 64,
        num_classes: int = 4,
        dropout_rate: float = 0.20
    ):
        super().__init__()
        self.text_dim = text_dim
        self.spatial_dim = spatial_dim
        self.num_classes = num_classes

        # 1. Text Projection MLP (Transforms 384-d MiniLM vectors into 64-d relational space)
        self.text_proj = nn.Sequential(
            nn.Linear(text_dim, 172),
            nn.LayerNorm(172),
            nn.ReLU(),
            nn.Linear(172, text_proj_dim),
            nn.LayerNorm(text_proj_dim),
            nn.ReLU()
        )

        # 2. Spatial Projection MLP (Transforms 15-d normalized geometry into 64-d relational space)
        self.spatial_proj = nn.Sequential(
            nn.Linear(spatial_dim, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Linear(64, spatial_proj_dim),
            nn.LayerNorm(spatial_proj_dim),
            nn.ReLU()
        )

        # Fused dimension: z_src (64) + z_tgt (64) + |z_src - z_tgt| (64) + (z_src * z_tgt) (64) + s_ij (64) = 320
        fused_dim = text_proj_dim * 4 + spatial_proj_dim

        # 3. Deep Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(fused_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(dropout_rate / 2.0),
            nn.Linear(128, num_classes)
        )

    def forward(
        self,
        spatial_feats: torch.Tensor,
        text_src: torch.Tensor,
        text_tgt: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.
        Args:
            spatial_feats: Tensor of shape (B, 15)
            text_src: Tensor of shape (B, 384)
            text_tgt: Tensor of shape (B, 384)
        Returns:
            Logits of shape (B, num_classes)
        """
        z_src = self.text_proj(text_src)
        z_tgt = self.text_proj(text_tgt)
        z_diff = torch.abs(z_src - z_tgt)
        z_prod = z_src * z_tgt

        s_ij = self.spatial_proj(spatial_feats)

        fused = torch.cat([z_src, z_tgt, z_diff, z_prod, s_ij], dim=-1)
        logits = self.classifier(fused)
        return logits

    @property
    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def extract_pairwise_geometry(
    bbox_i: Sequence[float],
    bbox_j: Sequence[float],
    page_w: float,
    page_h: float
) -> List[float]:
    """Compute normalized 15-dimensional spatial feature vector between two bounding boxes."""
    w_i = max(1.0, float(bbox_i[2] - bbox_i[0]))
    h_i = max(1.0, float(bbox_i[3] - bbox_i[1]))
    cx_i = float(bbox_i[0]) + w_i / 2.0
    cy_i = float(bbox_i[1]) + h_i / 2.0

    w_j = max(1.0, float(bbox_j[2] - bbox_j[0]))
    h_j = max(1.0, float(bbox_j[3] - bbox_j[1]))
    cx_j = float(bbox_j[0]) + w_j / 2.0
    cy_j = float(bbox_j[1]) + h_j / 2.0

    page_w = max(1.0, float(page_w))
    page_h = max(1.0, float(page_h))

    norm_i = [bbox_i[0] / page_w, bbox_i[1] / page_h, bbox_i[2] / page_w, bbox_i[3] / page_h]
    norm_j = [bbox_j[0] / page_w, bbox_j[1] / page_h, bbox_j[2] / page_w, bbox_j[3] / page_h]

    delta_x = (cx_j - cx_i) / page_w
    delta_y = (cy_j - cy_i) / page_h
    dist = math.sqrt(delta_x**2 + delta_y**2)
    angle = math.atan2(delta_y, delta_x) / math.pi

    # Intersection over Union
    ixmin = max(bbox_i[0], bbox_j[0])
    iymin = max(bbox_i[1], bbox_j[1])
    ixmax = min(bbox_i[2], bbox_j[2])
    iymax = min(bbox_i[3], bbox_j[3])
    iw = max(0.0, ixmax - ixmin)
    ih = max(0.0, iymax - iymin)
    inter = iw * ih
    union = (w_i * h_i) + (w_j * h_j) - inter
    iou = inter / max(1.0, union)

    log_w = math.log(w_i / w_j)
    log_h = math.log(h_i / h_j)

    return [
        norm_i[0], norm_i[1], norm_i[2], norm_i[3],
        norm_j[0], norm_j[1], norm_j[2], norm_j[3],
        delta_x, delta_y, dist, angle, iou, log_w, log_h
    ]


class SREdgeNetEngine:
    """Inference and evaluation engine for SR-EdgeNet."""

    def __init__(
        self,
        checkpoint_path: Optional[str] = "models/structure/sr_edge_net.pt",
        device: str = "cpu"
    ):
        self.device = torch.device(device)
        self.model = SREdgeClassifier().to(self.device)
        self.checkpoint_path = checkpoint_path
        self.is_loaded = False

        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load_checkpoint(checkpoint_path)

    def load_checkpoint(self, path: str) -> None:
        """Load trained model weights from disk."""
        state = torch.load(path, map_location=self.device, weights_only=True)
        if "model_state_dict" in state:
            self.model.load_state_dict(state["model_state_dict"])
        else:
            self.model.load_state_dict(state)
        self.model.eval()
        self.is_loaded = True
        self.checkpoint_path = path

    def predict_pair(
        self,
        spatial_feat_15d: Sequence[float],
        text_src_emb: np.ndarray,
        text_tgt_emb: np.ndarray
    ) -> Tuple[str, float, Dict[str, float]]:
        """Predict structural relationship for a single directed block pair."""
        self.model.eval()
        with torch.no_grad():
            s_t = torch.tensor(np.asarray([spatial_feat_15d]), dtype=torch.float32, device=self.device)
            t_src = torch.tensor(np.asarray([text_src_emb]), dtype=torch.float32, device=self.device)
            t_tgt = torch.tensor(np.asarray([text_tgt_emb]), dtype=torch.float32, device=self.device)

            logits = self.model(s_t, t_src, t_tgt)
            probs = F.softmax(logits, dim=-1)[0].cpu().numpy()

            pred_id = int(np.argmax(probs))
            pred_label = SRClass.ID_TO_LABEL[pred_id]
            pred_conf = float(probs[pred_id])
            prob_dict = {SRClass.ID_TO_LABEL[i]: float(probs[i]) for i in range(4)}

            return pred_label, pred_conf, prob_dict
