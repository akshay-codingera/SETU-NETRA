"""
train.py: Training pipeline for ER-SP (Evidence Relevance and Sufficiency Predictor).

Features:
- Reproducible deterministic seeds.
- Precomputed frozen MiniLM text embeddings cache for high-speed CPU training.
- Collate function with variable multi-passage padding and attention masking.
- Multi-class Focal Loss (gamma=2.0) with class weighting for hard epistemic boundaries.
- ReduceLROnPlateau learning rate schedule and early stopping on validation Macro F1.
- Complete metric tracking and artifact generation.
"""

import os
import sys
import json
import time
import yaml
import glob
import random
from typing import Dict, Any, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

# Ensure 'src' is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from setu_netra.evidence.er_sp import (
    ERSPClassifier,
    ERClass,
    compute_pair_interaction_features
)


def set_seed(seed: int = 42):
    """Sets deterministic seeds across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(False)


def precompute_embeddings_cache(
    splits_dir: str,
    cache_path: str,
    model_name: str = "all-MiniLM-L6-v2",
    device: str = "cpu"
) -> Dict[str, np.ndarray]:
    """
    Extracts all unique texts across dataset splits and precomputes
    their normalized MiniLM embeddings.
    """
    if os.path.exists(cache_path):
        print(f"Loading cached embeddings from {cache_path}...")
        cache = torch.load(cache_path, map_location="cpu", weights_only=False)
        print(f"Loaded {len(cache)} unique cached embeddings.")
        return cache

    print(f"Extracting unique texts across {splits_dir} for embedding...")
    from sentence_transformers import SentenceTransformer

    unique_texts = set()
    for fpath in glob.glob(os.path.join(splits_dir, "*.jsonl")):
        with open(fpath, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                unique_texts.add(record["question"].strip())
                for passage in record.get("passages", []):
                    unique_texts.add(passage.strip())

    text_list = sorted(list(unique_texts))
    print(f"Found {len(text_list)} unique text elements. Encoding with {model_name} on {device}...")
    t0 = time.time()
    embedder = SentenceTransformer(model_name, device=device)
    embeddings = embedder.encode(text_list, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
    t_elapsed = time.time() - t0
    print(f"Encoded {len(text_list)} texts in {t_elapsed:.2f}s ({len(text_list)/max(0.01, t_elapsed):.1f} texts/sec).")

    cache = {text: emb.astype(np.float32) for text, emb in zip(text_list, embeddings)}
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    torch.save(cache, cache_path)
    print(f"Saved embedding cache to {cache_path}")
    return cache


class SETUERDataset(Dataset):
    """Dataset for Evidence Relevance and Sufficiency Prediction."""

    def __init__(
        self,
        jsonl_path: str,
        embedding_cache: Dict[str, np.ndarray]
    ):
        self.records = []
        with open(jsonl_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))

        self.cache = embedding_cache
        self.zero_vec = np.zeros(384, dtype=np.float32)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        rec = self.records[idx]
        q_text = rec["question"].strip()
        q_emb = self.cache.get(q_text, self.zero_vec)

        passages = rec.get("passages", [])
        if not passages:
            passages = [""]

        # Compute pair features for each passage: (K, 1537)
        feat_list = []
        for p_text in passages:
            p_text = p_text.strip()
            p_emb = self.cache.get(p_text, self.zero_vec)
            feat = compute_pair_interaction_features(q_emb, p_emb)
            feat_list.append(feat)

        feats_tensor = torch.tensor(np.asarray(feat_list), dtype=torch.float32)  # (K, 1537)
        label_id = rec["label_id"]

        return {
            "example_id": rec["example_id"],
            "features": feats_tensor,
            "label_id": label_id,
            "is_abstention": 1 if rec.get("is_abstention_expected", False) else 0
        }


def collate_variable_passages(batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
    """
    Collates a batch of variable K passage examples by padding up to max_k.
    Returns:
    - 'features': (batch_size, max_k, 1537)
    - 'mask': (batch_size, max_k)
    - 'labels': (batch_size,)
    """
    max_k = max(item["features"].size(0) for item in batch)
    feature_dim = batch[0]["features"].size(1)  # 1537
    batch_size = len(batch)

    padded_features = torch.zeros(batch_size, max_k, feature_dim, dtype=torch.float32)
    mask = torch.zeros(batch_size, max_k, dtype=torch.float32)
    labels = torch.zeros(batch_size, dtype=torch.long)

    for i, item in enumerate(batch):
        k = item["features"].size(0)
        padded_features[i, :k, :] = item["features"]
        mask[i, :k] = 1.0
        labels[i] = item["label_id"]

    return {
        "features": padded_features,
        "mask": mask,
        "labels": labels
    }


class FocalLoss(nn.Module):
    """
    Multi-class Focal Loss:
    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
    Down-weights easy examples and forces model to learn hard epistemic distinctions.
    """

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[torch.Tensor] = None,
        reduction: str = "mean"
    ):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.alpha)
        p_t = torch.exp(-ce_loss)
        focal_loss = ((1.0 - p_t) ** self.gamma) * ce_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss


def train_model(config_path: str = "training/evidence/config.yaml") -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)

    seed = cfg["training"].get("seed", 42)
    device = cfg["training"].get("device", "cpu")
    batch_size = cfg["training"].get("batch_size", 32)
    epochs = cfg["training"].get("epochs", 30)
    lr = float(cfg["training"].get("learning_rate", 8e-4))
    weight_decay = float(cfg["training"].get("weight_decay", 1e-4))
    gamma = float(cfg["training"].get("focal_gamma", 2.0))
    patience = cfg["training"].get("early_stopping_patience", 7)
    lr_patience = cfg["training"].get("lr_patience", 3)
    lr_factor = float(cfg["training"].get("lr_factor", 0.5))

    set_seed(seed)

    splits_dir = cfg["dataset"]["data_dir"]
    cache_path = cfg["dataset"]["embedding_cache"]
    out_dir = cfg["training"]["output_dir"]
    model_save_path = cfg["training"]["model_save_path"]
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 70)
    print("SETU-NETRA: R2 Evidence Relevance & Sufficiency Predictor (ER-SP)")
    print("=" * 70)

    # 1. Embeddings cache
    emb_cache = precompute_embeddings_cache(splits_dir, cache_path, device=device)

    # 2. Datasets
    train_f = os.path.join(splits_dir, cfg["dataset"]["train_file"])
    val_f = os.path.join(splits_dir, cfg["dataset"]["val_file"])

    train_dataset = SETUERDataset(train_f, emb_cache)
    val_dataset = SETUERDataset(val_f, emb_cache)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_variable_passages
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_variable_passages
    )

    print(f"Train samples: {len(train_dataset)} | Val samples: {len(val_dataset)} | Batch size: {batch_size}")

    # 3. Model
    model = ERSPClassifier(
        interaction_dim=cfg["model"]["interaction_dim"],
        proj_dim=cfg["model"]["proj_dim"],
        hidden_dim=cfg["model"]["hidden_dim"],
        num_classes=cfg["model"]["num_classes"],
        dropout=cfg["model"]["dropout"]
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Initialized ERSPClassifier with {total_params:,} trainable parameters.")

    # 4. Loss, Optimizer & Scheduler
    criterion = FocalLoss(gamma=gamma)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=lr_factor, patience=lr_patience
    )

    best_val_macro_f1 = 0.0
    best_val_acc = 0.0
    best_epoch = 0
    patience_counter = 0
    history = []

    print("\nStarting Training on CPU...")
    train_start_time = time.time()

    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        train_losses = []
        train_preds, train_trues = [], []

        for batch in train_loader:
            feats = batch["features"].to(device)
            mask = batch["mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            logits = model(feats, mask=mask)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_losses.append(loss.item())
            preds = torch.argmax(logits, dim=-1).cpu().numpy()
            train_preds.extend(preds)
            train_trues.extend(labels.cpu().numpy())

        epoch_train_loss = float(np.mean(train_losses))
        train_acc = float(accuracy_score(train_trues, train_preds))
        train_f1 = float(f1_score(train_trues, train_preds, average="macro", zero_division=0))

        # Validation
        model.eval()
        val_losses = []
        val_preds, val_trues = [], []

        with torch.no_grad():
            for batch in val_loader:
                feats = batch["features"].to(device)
                mask = batch["mask"].to(device)
                labels = batch["labels"].to(device)

                logits = model(feats, mask=mask)
                loss = criterion(logits, labels)
                val_losses.append(loss.item())

                preds = torch.argmax(logits, dim=-1).cpu().numpy()
                val_preds.extend(preds)
                val_trues.extend(labels.cpu().numpy())

        epoch_val_loss = float(np.mean(val_losses))
        val_acc = float(accuracy_score(val_trues, val_preds))
        val_f1 = float(f1_score(val_trues, val_preds, average="macro", zero_division=0))
        epoch_sec = time.time() - t_epoch_start

        scheduler.step(val_f1)
        current_lr = optimizer.param_groups[0]["lr"]

        epoch_log = {
            "epoch": epoch,
            "train_loss": epoch_train_loss,
            "train_acc": train_acc,
            "train_macro_f1": train_f1,
            "val_loss": epoch_val_loss,
            "val_acc": val_acc,
            "val_macro_f1": val_f1,
            "lr": current_lr,
            "duration_sec": epoch_sec
        }
        history.append(epoch_log)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} [{epoch_sec:.2f}s] - "
            f"Train Loss: {epoch_train_loss:.4f} Acc: {train_acc*100:.2f}% F1: {train_f1:.4f} | "
            f"Val Loss: {epoch_val_loss:.4f} Acc: {val_acc*100:.2f}% F1: {val_f1:.4f} | LR: {current_lr:.6f}"
        )

        # Checkpoint on best validation Macro F1
        if val_f1 > best_val_macro_f1:
            best_val_macro_f1 = val_f1
            best_val_acc = val_acc
            best_epoch = epoch
            patience_counter = 0

            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_macro_f1": val_f1,
                "val_acc": val_acc,
                "config": cfg,
                "classes": ERClass.ALL,
                "num_classes": ERClass.NUM_CLASSES
            }
            torch.save(checkpoint, model_save_path)
            print(f"  -> New best checkpoint saved to {model_save_path} (Val F1: {val_f1:.4f}, Acc: {val_acc*100:.2f}%)")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping triggered after {epoch} epochs (patience={patience}). Best epoch: {best_epoch}")
                break

    total_training_sec = time.time() - train_start_time
    print("\n" + "=" * 70)
    print(f"Training Complete in {total_training_sec:.2f}s!")
    print(f"Best Validation Epoch: {best_epoch} | Best Val Macro F1: {best_val_macro_f1:.4f} | Best Val Acc: {best_val_acc*100:.2f}%")
    print(f"Final Model Checkpoint: {model_save_path}")
    print("=" * 70)

    # Save training history
    history_path = os.path.join(out_dir, "training_history.json")
    with open(history_path, "w", encoding="utf-8") as fp:
        json.dump({
            "total_training_time_sec": total_training_sec,
            "best_epoch": best_epoch,
            "best_val_macro_f1": best_val_macro_f1,
            "best_val_accuracy": best_val_acc,
            "trainable_parameters": total_params,
            "epochs_run": len(history),
            "history": history
        }, fp, indent=2)

    return {
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_macro_f1,
        "best_val_acc": best_val_acc,
        "total_training_time_sec": total_training_sec,
        "model_save_path": model_save_path,
        "history_path": history_path
    }


if __name__ == "__main__":
    train_model()
