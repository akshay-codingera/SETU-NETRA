"""
test_dataset_loader.py: Unit tests for SETUSREdgeDataset and DataLoader.
"""

import sys
import torch

sys.path.insert(0, "training/structure")
from config import SREdgeNetConfig
from dataset_loader import SETUSREdgeDataset, get_dataloader


def test_loader():
    cfg = SREdgeNetConfig(batch_size=32)

    # Test FUNSD dataset
    funsd_path = "training/datasets/SETU-SR/FUNSD/funsd_edges_train.jsonl"
    funsd_ds = SETUSREdgeDataset(funsd_path, config=cfg)
    assert len(funsd_ds) > 0, "FUNSD dataset empty!"
    x0, y0, meta0 = funsd_ds[0]
    print(f"Sample 0 from FUNSD: x={x0.shape}, y={y0.item()} ({cfg.id_to_label[y0.item()]}), doc={meta0['doc_id']}")
    assert x0.shape == torch.Size([15]), f"Expected shape [15], got {x0.shape}"

    # Test Synthetic dataset
    synth_path = "training/datasets/SETU-SR/synthetic/synthetic_edges.jsonl"
    synth_ds = SETUSREdgeDataset(synth_path, config=cfg)
    assert len(synth_ds) > 0, "Synthetic dataset empty!"
    x1, y1, meta1 = synth_ds[0]
    print(f"Sample 0 from Synthetic: x={x1.shape}, y={y1.item()} ({cfg.id_to_label[y1.item()]}), doc={meta1['doc_id']}")
    assert x1.shape == torch.Size([15]), f"Expected shape [15], got {x1.shape}"

    # Test DataLoader batching
    loader = get_dataloader(synth_path, config=cfg, batch_size=64, shuffle=True)
    batch_xs, batch_ys, batch_metas = next(iter(loader))
    print(f"DataLoader Batch: xs={batch_xs.shape}, ys={batch_ys.shape}, len(metas)={len(batch_metas)}")
    assert batch_xs.shape == torch.Size([64, 15])
    assert batch_ys.shape == torch.Size([64])

    print("Dataset and DataLoader tests PASSED successfully.")


if __name__ == "__main__":
    test_loader()
