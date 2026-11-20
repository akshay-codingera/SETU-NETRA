"""
er_sp.py: Evidence Relevance and Sufficiency Predictor (ER-SP) for SETU-NETRA.

Architecture:
- Frozen MiniLM (384-d) dense semantic embeddings for queries and passages.
- Pairwise interaction tensor: [q, p, |q - p|, q * p, cos(q, p)] (1,537-d).
- Multi-passage attention pooling layer across variable evidence passages (K >= 1).
- Deep epistemic classification head (~559k parameters).
- Five-class taxonomy:
  0: SUFFICIENT (Jointly/individually provides complete factual grounding to answer)
  1: PARTIALLY_SUFFICIENT (Semantically relevant context present, but critical premise is missing)
  2: CONTRADICTORY (Passage directly asserts an opposite polarity, contradicting question premises)
  3: IRRELEVANT (Passage is from an unrelated domain with zero factual grounding)
  4: UNVERIFIABLE (Inquiry posits subjective, speculative, or unanswerable claims given evidence)
"""

import os
import math
from typing import List, Dict, Any, Optional, Tuple, Sequence, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class ERClass:
    """Taxonomy of epistemic evidence relevance and sufficiency classes."""
    SUFFICIENT = "SUFFICIENT"
    PARTIALLY_SUFFICIENT = "PARTIALLY_SUFFICIENT"
    CONTRADICTORY = "CONTRADICTORY"
    IRRELEVANT = "IRRELEVANT"
    UNVERIFIABLE = "UNVERIFIABLE"

    ALL = [
        SUFFICIENT,
        PARTIALLY_SUFFICIENT,
        CONTRADICTORY,
        IRRELEVANT,
        UNVERIFIABLE
    ]

    LABEL_TO_ID = {
        SUFFICIENT: 0,
        PARTIALLY_SUFFICIENT: 1,
        CONTRADICTORY: 2,
        IRRELEVANT: 3,
        UNVERIFIABLE: 4
    }

    ID_TO_LABEL = {v: k for k, v in LABEL_TO_ID.items()}
    NUM_CLASSES = len(ALL)


def compute_pair_interaction_features(
    q_emb: np.ndarray,
    p_emb: np.ndarray
) -> np.ndarray:
    """
    Computes dense 1,537-dimensional question-passage interaction features:
    [q, p, |q - p|, q * p, cos(q, p)]
    """
    q = np.asarray(q_emb, dtype=np.float32).flatten()
    p = np.asarray(p_emb, dtype=np.float32).flatten()

    norm_q = np.linalg.norm(q)
    norm_p = np.linalg.norm(p)
    cos_sim = float(np.dot(q, p) / (norm_q * norm_p + 1e-8))

    diff = np.abs(q - p)
    prod = q * p

    feats = np.concatenate([q, p, diff, prod, np.array([cos_sim], dtype=np.float32)], axis=0)
    return feats


class ERSPClassifier(nn.Module):
    """
    Lightweight neural model distinguishing semantic relevance from logical sufficiency.
    Aggregates multi-passage evidence using attention pooling and max pooling.
    """

    def __init__(
        self,
        interaction_dim: int = 1537,
        proj_dim: int = 256,
        hidden_dim: int = 128,
        num_classes: int = 5,
        dropout: float = 0.2
    ):
        super().__init__()
        self.interaction_dim = interaction_dim
        self.proj_dim = proj_dim
        self.hidden_dim = hidden_dim
        self.num_classes = num_classes

        # 1. Interaction Projection Layer: 1,537-d -> 256-d
        self.proj = nn.Sequential(
            nn.Linear(interaction_dim, proj_dim),
            nn.LayerNorm(proj_dim),
            nn.GELU(),
            nn.Dropout(dropout * 0.5)
        )

        # 2. Multi-Passage Attention Scorer: 256-d -> 1-d
        self.attn_scorer = nn.Linear(proj_dim, 1)

        # 3. Epistemic Classification MLP: (proj_dim * 2 = 512) -> 256 -> 128 -> 5
        pooled_dim = proj_dim * 2
        self.classifier = nn.Sequential(
            nn.Linear(pooled_dim, proj_dim),
            nn.LayerNorm(proj_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(proj_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(
        self,
        interaction_tensor: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass.
        interaction_tensor: (batch_size, K, 1537) or (batch_size, 1537)
        mask: (batch_size, K) boolean or float tensor indicating valid passages (1 = valid, 0 = pad)
        Returns: logits of shape (batch_size, num_classes)
        """
        if interaction_tensor.dim() == 2:
            # Single passage per query: (B, 1537) -> (B, 1, 1537)
            interaction_tensor = interaction_tensor.unsqueeze(1)

        batch_size, k_passages, _ = interaction_tensor.shape

        # Step 1: Project each passage interaction into 256-d
        projected = self.proj(interaction_tensor)  # (B, K, 256)

        # Step 2: Multi-Passage Evidence Aggregation
        if k_passages == 1:
            # Fast path for single passage
            c_attn = projected.squeeze(1)  # (B, 256)
            c_max = projected.squeeze(1)   # (B, 256)
        else:
            # Attention pooling
            attn_logits = self.attn_scorer(projected)  # (B, K, 1)
            if mask is not None:
                mask_expanded = mask.unsqueeze(-1)  # (B, K, 1)
                attn_logits = attn_logits.masked_fill(~mask_expanded.bool(), -1e9)

            attn_weights = F.softmax(attn_logits, dim=1)  # (B, K, 1)
            c_attn = torch.sum(attn_weights * projected, dim=1)  # (B, 256)

            if mask is not None:
                # Masked max pooling
                masked_proj = projected.masked_fill(~mask.unsqueeze(-1).bool(), -1e9)
                c_max = torch.max(masked_proj, dim=1)[0]
            else:
                c_max = torch.max(projected, dim=1)[0]  # (B, 256)

        pooled_evidence = torch.cat([c_attn, c_max], dim=-1)  # (B, 512)

        # Step 3: Classification Head
        logits = self.classifier(pooled_evidence)  # (B, 5)
        return logits


class ERSPPredictor:
    """Production inference and evaluation predictor for ER-SP."""

    def __init__(
        self,
        checkpoint_path: Optional[str] = "models/evidence/er_sp.pt",
        device: str = "cpu",
        confidence_threshold: float = 0.50
    ):
        self.device = torch.device(device)
        self.model = ERSPClassifier().to(self.device)
        self.checkpoint_path = checkpoint_path
        self.confidence_threshold = confidence_threshold
        self.is_loaded = False
        self._embedder = None

        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load_checkpoint(checkpoint_path)

    def load_checkpoint(self, path: str) -> None:
        """Loads trained weights from checkpoint."""
        state = torch.load(path, map_location=self.device, weights_only=True)
        if "model_state_dict" in state:
            self.model.load_state_dict(state["model_state_dict"])
        else:
            self.model.load_state_dict(state)
        self.model.eval()
        self.is_loaded = True
        self.checkpoint_path = path

    def _get_embedder(self):
        """Lazy loader for SentenceTransformer to conserve memory and startup time."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        return self._embedder

    def predict_from_embeddings(
        self,
        q_emb: np.ndarray,
        p_embs: Sequence[np.ndarray]
    ) -> Dict[str, Any]:
        """
        Runs epistemic prediction given precomputed MiniLM embeddings.
        q_emb: (384,)
        p_embs: list of (384,) ndarrays
        """
        self.model.eval()
        if not p_embs:
            # Zero passages retrieved -> immediately IRRELEVANT / Abstain
            return {
                "label": ERClass.IRRELEVANT,
                "label_id": ERClass.LABEL_TO_ID[ERClass.IRRELEVANT],
                "confidence": 1.0,
                "probabilities": {cls: (1.0 if cls == ERClass.IRRELEVANT else 0.0) for cls in ERClass.ALL},
                "should_abstain": True,
                "abstention_reason": "No evidence passages provided.",
                "retrieval_cosine": 0.0
            }

        feats_list = []
        cosines = []
        for p in p_embs:
            feat = compute_pair_interaction_features(q_emb, p)
            feats_list.append(feat)
            cosines.append(float(feat[-1]))

        interaction_tensor = torch.tensor(
            np.asarray([feats_list]),
            dtype=torch.float32,
            device=self.device
        )  # (1, K, 1537)

        with torch.no_grad():
            logits = self.model(interaction_tensor)
            probs = F.softmax(logits, dim=-1)[0].cpu().numpy()

        pred_id = int(np.argmax(probs))
        pred_label = ERClass.ID_TO_LABEL[pred_id]
        pred_conf = float(probs[pred_id])
        max_cosine = max(cosines) if cosines else 0.0

        # Abstention Policy Logic
        should_abstain = False
        abstention_reason = None

        if pred_label != ERClass.SUFFICIENT:
            should_abstain = True
            if pred_label == ERClass.PARTIALLY_SUFFICIENT:
                abstention_reason = "Retrieved passages contain necessary context but lack critical conclusive premises."
            elif pred_label == ERClass.CONTRADICTORY:
                abstention_reason = "Retrieved passages explicitly contradict the question premises."
            elif pred_label == ERClass.IRRELEVANT:
                abstention_reason = "Retrieved passages lack semantic and factual relevance to the query."
            elif pred_label == ERClass.UNVERIFIABLE:
                abstention_reason = "The inquiry posits subjective, speculative, or unanswerable claims given available evidence."
        elif pred_conf < self.confidence_threshold:
            should_abstain = True
            abstention_reason = f"Epistemic confidence ({pred_conf:.3f}) below reliability threshold ({self.confidence_threshold:.3f})."

        return {
            "label": pred_label,
            "label_id": pred_id,
            "confidence": pred_conf,
            "probabilities": {ERClass.ID_TO_LABEL[i]: float(probs[i]) for i in range(ERClass.NUM_CLASSES)},
            "should_abstain": should_abstain,
            "abstention_reason": abstention_reason,
            "retrieval_cosine": max_cosine
        }

    def predict(
        self,
        question: str,
        passages: Sequence[str]
    ) -> Dict[str, Any]:
        """
        End-to-end epistemic prediction from raw text strings.
        Encodes texts with frozen MiniLM and computes evidence sufficiency.
        """
        embedder = self._get_embedder()
        q_emb = embedder.encode(question, normalize_embeddings=True)
        p_embs = [embedder.encode(p, normalize_embeddings=True) for p in passages]
        return self.predict_from_embeddings(q_emb, p_embs)
