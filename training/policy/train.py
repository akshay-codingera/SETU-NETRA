"""
train.py: Training pipeline for CM-RP (Contextual Multi-Strategy Reasoning Policy).

Features:
- PyTorch CPU-compatible contextual policy training.
- 423-dimensional multimodal context input vectors.
- Action feasibility masking with constrained softmax.
- Multi-class Focal Loss (gamma=1.5) with early stopping on validation Macro F1.
- Detailed training history and model artifact serialization.
"""

import os
import sys
import json
import time
import yaml
import random
from typing import Dict, Any, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score

# Ensure 'src' is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from setu_netra.policy.cm_rp import (
    CMPolicyNetwork,
    StrategyAction,
    ACTION_TO_ID,
    ID_TO_ACTION,
    NUM_ACTIONS
)


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(False)


class SETUCMDataset(Dataset):
    """Dataset for Contextual Multi-Strategy Reasoning Policy."""

    def __init__(self, jsonl_path: str):
        self.records = []
        with open(jsonl_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        rec = self.records[idx]
        feat_vec = torch.tensor(rec["context_features"], dtype=torch.float32)
        mask_vec = torch.tensor(rec["action_mask"], dtype=torch.float32)
        action_id = torch.tensor(rec["action_id"], dtype=torch.long)

        return {
            "features": feat_vec,
            "mask": mask_vec,
            "target": action_id
        }


class FocalLoss(nn.Module):
    """Multi-class Focal Loss for policy optimization."""

    def __init__(self, gamma: float = 1.5, reduction: str = "mean"):
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        p_t = torch.exp(-ce_loss)
        focal_loss = ((1.0 - p_t) ** self.gamma) * ce_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss


def train_policy(config_path: str = "training/policy/config.yaml") -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)

    seed = cfg["training"].get("seed", 42)
    device = cfg["training"].get("device", "cpu")
    batch_size = cfg["training"].get("batch_size", 32)
    epochs = cfg["training"].get("epochs", 35)
    lr = float(cfg["training"].get("learning_rate", 1e-3))
    weight_decay = float(cfg["training"].get("weight_decay", 1e-4))
    gamma = float(cfg["training"].get("focal_gamma", 1.5))
    patience = cfg["training"].get("early_stopping_patience", 8)
    lr_patience = cfg["training"].get("lr_patience", 3)
    lr_factor = float(cfg["training"].get("lr_factor", 0.5))

    set_seed(seed)

    splits_dir = cfg["dataset"]["data_dir"]
    out_dir = cfg["training"]["output_dir"]
    model_save_path = cfg["training"]["model_save_path"]
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 70)
    print("SETU-NETRA: R3 Contextual Multi-Strategy Reasoning Policy (CM-RP)")
    print("=" * 70)

    # 1. Datasets & Loaders
    train_path = os.path.join(splits_dir, cfg["dataset"]["train_file"])
    val_path = os.path.join(splits_dir, cfg["dataset"]["val_file"])

    train_dataset = SETUCMDataset(train_path)
    val_dataset = SETUCMDataset(val_path)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    print(f"Train samples: {len(train_dataset)} | Val samples: {len(val_dataset)} | Batch size: {batch_size}")

    # 2. Model Initialization
    model = CMPolicyNetwork(
        input_dim=cfg["model"]["input_dim"],
        hidden_dim1=cfg["model"]["hidden_dim1"],
        hidden_dim2=cfg["model"]["hidden_dim2"],
        num_actions=cfg["model"]["num_actions"],
        dropout=cfg["model"]["dropout"]
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Initialized CMPolicyNetwork with {total_params:,} trainable parameters.")

    # 3. Optimization Setup
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

    print("\nStarting Policy Optimization on CPU...")
    train_start_time = time.time()

    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        train_losses = []
        train_preds, train_trues = [], []

        for batch in train_loader:
            feats = batch["features"].to(device)
            mask = batch["mask"].to(device)
            targets = batch["target"].to(device)

            optimizer.zero_grad()
            logits = model(feats, action_mask=mask)
            loss = criterion(logits, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_losses.append(loss.item())
            preds = torch.argmax(logits, dim=-1).cpu().numpy()
            train_preds.extend(preds)
            train_trues.extend(targets.cpu().numpy())

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
                targets = batch["target"].to(device)

                logits = model(feats, action_mask=mask)
                loss = criterion(logits, targets)
                val_losses.append(loss.item())

                preds = torch.argmax(logits, dim=-1).cpu().numpy()
                val_preds.extend(preds)
                val_trues.extend(targets.cpu().numpy())

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
                "actions": StrategyAction.get_all(),
                "action_to_id": ACTION_TO_ID,
                "input_dim": cfg["model"]["input_dim"],
                "total_parameters": total_params
            }
            torch.save(checkpoint, model_save_path)
            print(f"  -> Best checkpoint saved to {model_save_path} (Val F1: {val_f1:.4f}, Acc: {val_acc*100:.2f}%)")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping triggered after {epoch} epochs. Best epoch: {best_epoch}")
                break

    total_training_sec = time.time() - train_start_time
    print("\n" + "=" * 70)
    print(f"Policy Training Complete in {total_training_sec:.2f}s!")
    print(f"Best Epoch: {best_epoch} | Best Val Macro F1: {best_val_macro_f1:.4f} | Best Val Acc: {best_val_acc*100:.2f}%")
    print(f"Saved Checkpoint: {model_save_path}")
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
    train_policy()
