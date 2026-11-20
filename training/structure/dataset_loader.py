"""
dataset_loader.py: PyTorch Dataset and DataLoader for SETU-SR Edge classification.
"""

import json
import torch
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Any, Tuple, Optional
from config import SREdgeNetConfig


class SETUSREdgeDataset(Dataset):
    """PyTorch Dataset loading SETU-SR spatial-relational edge records."""

    def __init__(
        self,
        jsonl_path: str,
        config: Optional[SREdgeNetConfig] = None,
        max_samples: Optional[int] = None
    ):
        self.jsonl_path = jsonl_path
        self.config = config or SREdgeNetConfig()
        self.records: List[Dict[str, Any]] = []

        with open(jsonl_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))
                if max_samples and len(self.records) >= max_samples:
                    break

        print(f"Loaded {len(self.records)} edge records from {jsonl_path}")

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        record = self.records[idx]
        raw_feats = record["relative_features"]["feature_vector"]
        label_str = record["relationship_label"]
        label_id = self.config.label_to_id.get(label_str, 3)  # default NONE

        x = torch.tensor(raw_feats, dtype=torch.float32)
        y = torch.tensor(label_id, dtype=torch.long)

        metadata = {
            "doc_id": record["doc_id"],
            "page_id": record["page_id"],
            "source_block_id": record["source_block_id"],
            "target_block_id": record["target_block_id"],
            "source_text": record["source_text"],
            "target_text": record["target_text"],
            "relationship_label": label_str,
            "annotation_source": record["annotation_source"]
        }

        return x, y, metadata


def get_dataloader(
    jsonl_path: str,
    config: Optional[SREdgeNetConfig] = None,
    shuffle: bool = True,
    batch_size: Optional[int] = None
) -> DataLoader:
    """Helper factory function to create a PyTorch DataLoader."""
    cfg = config or SREdgeNetConfig()
    ds = SETUSREdgeDataset(jsonl_path, config=cfg)
    bs = batch_size or cfg.batch_size
    return DataLoader(
        ds,
        batch_size=bs,
        shuffle=shuffle,
        num_workers=cfg.num_workers,
        collate_fn=collate_edges
    )


def collate_edges(batch):
    xs = torch.stack([item[0] for item in batch], dim=0)
    ys = torch.stack([item[1] for item in batch], dim=0)
    metas = [item[2] for item in batch]
    return xs, ys, metas
