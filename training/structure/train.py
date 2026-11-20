"""
train.py: Training pipeline for SR-EdgeNet spatial-relational edge classifier.

Supports:
- Condition A: Combined data (FUNSD + Synthetic) -> primary model
- Condition B: FUNSD-only data
- Condition C: Synthetic-only data
- Early stopping, validation monitoring, focal loss class imbalance handling,
  and best checkpoint saving.
"""

import os
import sys
import time
import json
import random
import yaml
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Ensure src and training/structure are on sys.path
sys.path.insert(0, "src")
sys.path.insert(0, "training/structure")

from setu_netra.structure.sr_edge_net import SREdgeClassifier, FocalLoss, SRClass
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class CachedEdgeDataset(Dataset):
    """Fast in-memory dataset mapping precomputed 384-d embeddings and 15-d geometry."""

    def __init__(
        self,
        records: List[Dict[str, Any]],
        embedding_dict: Dict[str, np.ndarray],
        label_to_id: Dict[str, int]
    ):
        self.records = records
        self.label_to_id = label_to_id
        
        # Pre-allocate tensors for speed
        n = len(records)
        self.spatial_tensor = torch.zeros((n, 15), dtype=torch.float32)
        self.src_emb_tensor = torch.zeros((n, 384), dtype=torch.float32)
        self.tgt_emb_tensor = torch.zeros((n, 384), dtype=torch.float32)
        self.labels_tensor = torch.zeros(n, dtype=torch.long)
        self.doc_ids = []

        zero_vec = np.zeros(384, dtype=np.float32)

        for i, r in enumerate(records):
            feats = r["relative_features"]["feature_vector"]
            self.spatial_tensor[i] = torch.tensor(feats, dtype=torch.float32)

            src_txt = r["source_text"].strip()
            tgt_txt = r["target_text"].strip()
            self.src_emb_tensor[i] = torch.tensor(embedding_dict.get(src_txt, zero_vec), dtype=torch.float32)
            self.tgt_emb_tensor[i] = torch.tensor(embedding_dict.get(tgt_txt, zero_vec), dtype=torch.float32)

            lbl = r["relationship_label"]
            self.labels_tensor[i] = self.label_to_id.get(lbl, 3)
            self.doc_ids.append(r["doc_id"])

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        return (
            self.spatial_tensor[idx],
            self.src_emb_tensor[idx],
            self.tgt_emb_tensor[idx],
            self.labels_tensor[idx]
        )


def build_embedding_cache(
    all_texts: List[str],
    cache_path: str = "training/structure/embedding_cache.pt",
    batch_size: int = 256
) -> Dict[str, np.ndarray]:
    """Precompute and cache MiniLM embeddings for all unique texts."""
    unique_texts = sorted(list(set(t.strip() for t in all_texts if t.strip())))
    print(f"Building text embedding cache for {len(unique_texts)} unique strings...")

    if os.path.exists(cache_path):
        try:
            cached = torch.load(cache_path, weights_only=False)
            # Check if all texts present
            missing = [t for t in unique_texts if t not in cached]
            if not missing:
                print(f"Loaded valid embedding cache from {cache_path} ({len(cached)} items)")
                return cached
            else:
                print(f"Cache missing {len(missing)} items, updating...")
        except Exception as e:
            print(f"Cache load warning: {e}, recomputing...")

    eng = NeuralSentenceEmbeddingEngine()
    cached = {}

    for i in range(0, len(unique_texts), batch_size):
        chunk = unique_texts[i:i + batch_size]
        vecs = eng.embed_texts(chunk)
        for t, v in zip(chunk, vecs):
            cached[t] = v
        if (i // batch_size) % 5 == 0 or i + batch_size >= len(unique_texts):
            print(f"  Embedded {min(i + batch_size, len(unique_texts))}/{len(unique_texts)} texts")

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    torch.save(cached, cache_path)
    print(f"Embedding cache saved to {cache_path}")
    return cached


def compute_metrics(
    all_preds: np.ndarray,
    all_targets: np.ndarray,
    num_classes: int = 4
) -> Dict[str, Any]:
    """Compute Accuracy, Macro Precision, Recall, F1 and per-class metrics."""
    acc = float(np.mean(all_preds == all_targets))
    
    # Confusion Matrix
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for p, t in zip(all_preds, all_targets):
        cm[t, p] += 1

    per_class = {}
    precisions = []
    recalls = []
    f1s = []

    for c in range(num_classes):
        c_name = SRClass.ID_TO_LABEL[c]
        tp = float(cm[c, c])
        fp = float(np.sum(cm[:, c]) - tp)
        fn = float(np.sum(cm[c, :]) - tp)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        per_class[c_name] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": int(np.sum(cm[c, :]))
        }

    macro_p = float(np.mean(precisions))
    macro_r = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))

    return {
        "accuracy": round(acc, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist()
    }


def train_model(
    train_records: List[Dict[str, Any]],
    val_records: List[Dict[str, Any]],
    embedding_dict: Dict[str, np.ndarray],
    config: Dict[str, Any],
    checkpoint_save_path: str,
    condition_name: str = "Combined"
) -> Dict[str, Any]:
    set_seed(config.get("seed", 42))
    device = torch.device(config.get("device", "cpu"))

    model_cfg = config.get("model", {})
    train_cfg = config.get("training", {})

    label_to_id = SRClass.LABEL_TO_ID
    train_ds = CachedEdgeDataset(train_records, embedding_dict, label_to_id)
    val_ds = CachedEdgeDataset(val_records, embedding_dict, label_to_id)

    batch_size = train_cfg.get("batch_size", 64)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = SREdgeClassifier(
        text_dim=model_cfg.get("text_dim", 384),
        text_proj_dim=model_cfg.get("text_proj_dim", 64),
        spatial_dim=model_cfg.get("spatial_dim", 15),
        spatial_proj_dim=model_cfg.get("spatial_proj_dim", 64),
        num_classes=model_cfg.get("num_classes", 4),
        dropout_rate=model_cfg.get("dropout_rate", 0.20)
    ).to(device)

    print(f"\n=======================================================")
    print(f"Starting Training: Condition [{condition_name}]")
    print(f"Model Parameters: {model.parameter_count:,}")
    print(f"Train samples: {len(train_ds):,}, Val samples: {len(val_ds):,}")
    print(f"Target Checkpoint: {checkpoint_save_path}")
    print(f"=======================================================")

    class_weights = torch.tensor(train_cfg.get("class_weights", [1.2, 1.0, 1.5, 0.4]), dtype=torch.float32, device=device)
    loss_fn = FocalLoss(gamma=train_cfg.get("focal_gamma", 2.0), weight=class_weights)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(train_cfg.get("learning_rate", 1e-3)),
        weight_decay=float(train_cfg.get("weight_decay", 1e-4))
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=float(train_cfg.get("lr_scheduler_factor", 0.5)),
        patience=int(train_cfg.get("lr_scheduler_patience", 2))
    )

    epochs = int(train_cfg.get("epochs", 15))
    early_stopping_patience = int(train_cfg.get("early_stopping_patience", 4))

    best_val_f1 = -1.0
    best_epoch = -1
    best_metrics = {}
    patience_counter = 0
    history = []

    start_train_time = time.perf_counter()

    for epoch in range(1, epochs + 1):
        epoch_start = time.perf_counter()
        model.train()
        train_loss = 0.0

        for s_b, t_src_b, t_tgt_b, y_b in train_loader:
            s_b, t_src_b, t_tgt_b, y_b = s_b.to(device), t_src_b.to(device), t_tgt_b.to(device), y_b.to(device)

            optimizer.zero_grad()
            logits = model(s_b, t_src_b, t_tgt_b)
            loss = loss_fn(logits, y_b)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(y_b)

        train_loss = train_loss / len(train_ds)

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_preds = []
        val_targets = []

        with torch.no_grad():
            for s_b, t_src_b, t_tgt_b, y_b in val_loader:
                s_b, t_src_b, t_tgt_b, y_b = s_b.to(device), t_src_b.to(device), t_tgt_b.to(device), y_b.to(device)
                logits = model(s_b, t_src_b, t_tgt_b)
                loss = loss_fn(logits, y_b)
                val_loss += loss.item() * len(y_b)

                preds = torch.argmax(logits, dim=-1).cpu().numpy()
                val_preds.extend(preds)
                val_targets.extend(y_b.cpu().numpy())

        val_loss = val_loss / len(val_ds)
        val_preds = np.array(val_preds)
        val_targets = np.array(val_targets)

        metrics = compute_metrics(val_preds, val_targets, num_classes=4)
        val_f1 = metrics["macro_f1"]
        val_acc = metrics["accuracy"]
        scheduler.step(val_f1)

        epoch_duration = time.perf_counter() - epoch_start
        lr = optimizer.param_groups[0]["lr"]

        print(
            f"Epoch {epoch:2d}/{epochs:2d} ({epoch_duration:.1f}s) | "
            f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
            f"Val Acc: {val_acc:.4f} | Val Macro F1: {val_f1:.4f} | LR: {lr:.2e}"
        )

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": val_acc,
            "val_macro_f1": val_f1,
            "lr": lr
        })

        # Checkpoint if best
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            best_metrics = metrics
            patience_counter = 0

            os.makedirs(os.path.dirname(checkpoint_save_path), exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "metrics": metrics,
                "config": config,
                "condition": condition_name
            }, checkpoint_save_path)
            print(f"  >>> Best checkpoint saved to {checkpoint_save_path} (Macro F1 = {val_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                print(f"Early stopping triggered at epoch {epoch} (no improvement in {early_stopping_patience} epochs).")
                break

    total_duration = time.perf_counter() - start_train_time
    print(f"\nCondition [{condition_name}] Training Complete in {total_duration:.1f}s. Best Epoch: {best_epoch} (Macro F1: {best_val_f1:.4f})")

    return {
        "condition": condition_name,
        "checkpoint_path": checkpoint_save_path,
        "parameters": model.parameter_count,
        "best_epoch": best_epoch,
        "best_macro_f1": best_val_f1,
        "best_metrics": best_metrics,
        "training_duration_sec": round(total_duration, 2),
        "history": history
    }


def main():
    with open("training/structure/config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 1. Load splits
    def load_jsonl(p):
        with open(p, "r", encoding="utf-8") as fp:
            return [json.loads(line) for line in fp if line.strip()]

    train_data = load_jsonl(cfg["data"]["train_split"])
    val_data = load_jsonl(cfg["data"]["val_split"])
    test_synth_data = load_jsonl(cfg["data"]["test_synthetic"])
    test_indomain_data = load_jsonl(cfg["data"]["test_in_domain"])

    # 2. Collect all texts across dataset
    all_texts = []
    for split_records in [train_data, val_data, test_synth_data, test_indomain_data]:
        for r in split_records:
            all_texts.append(r["source_text"])
            all_texts.append(r["target_text"])

    emb_cache = build_embedding_cache(all_texts)

    # Prepare datasets for 3 conditions:
    # Condition 1: Combined
    res_comb = train_model(
        train_records=train_data,
        val_records=val_data,
        embedding_dict=emb_cache,
        config=cfg,
        checkpoint_save_path=cfg["checkpoints"]["primary_checkpoint"],
        condition_name="Combined (FUNSD + Synthetic)"
    )

    # Condition 2: FUNSD only
    funsd_train_records = [r for r in train_data if "funsd" in r["annotation_source"]]
    funsd_val_records = [r for r in val_data if "funsd" in r["annotation_source"]]
    res_funsd = train_model(
        train_records=funsd_train_records,
        val_records=funsd_val_records,
        embedding_dict=emb_cache,
        config=cfg,
        checkpoint_save_path=cfg["checkpoints"]["funsd_only_checkpoint"],
        condition_name="FUNSD Only"
    )

    # Condition 3: Synthetic only
    synth_train_records = [r for r in train_data if "synthetic" in r["annotation_source"]]
    synth_val_records = [r for r in val_data if "synthetic" in r["annotation_source"]]
    res_synth = train_model(
        train_records=synth_train_records,
        val_records=synth_val_records,
        embedding_dict=emb_cache,
        config=cfg,
        checkpoint_save_path=cfg["checkpoints"]["synth_only_checkpoint"],
        condition_name="Synthetic Only"
    )

    # Save summary
    summary_path = "models/structure/training_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fp:
        json.dump({
            "combined": res_comb,
            "funsd_only": res_funsd,
            "synthetic_only": res_synth
        }, fp, indent=2)

    print(f"\nAll training conditions completed. Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
