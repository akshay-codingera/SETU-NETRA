"""
assemble_splits.py: Combines FUNSD, Synthetic, and In-Domain datasets into canonical splits.
Performs data-quality audits and generates dataset_manifest.json.
"""

import os
import json
from typing import Dict, List, Any


def assemble_and_validate_dataset(
    funsd_train_path: str = "training/datasets/SETU-SR/FUNSD/funsd_edges_train.jsonl",
    funsd_test_path: str = "training/datasets/SETU-SR/FUNSD/funsd_edges_test.jsonl",
    synthetic_path: str = "training/datasets/SETU-SR/synthetic/synthetic_edges.jsonl",
    in_domain_path: str = "training/datasets/SETU-SR/in_domain/in_domain_edges.jsonl",
    splits_dir: str = "training/datasets/SETU-SR/splits",
    manifest_path: str = "training/datasets/SETU-SR/dataset_manifest.json"
):
    os.makedirs(splits_dir, exist_ok=True)

    print("--- 1. Loading Datasets ---")
    def load_jsonl(p):
        recs = []
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        recs.append(json.loads(line))
        return recs

    funsd_train = load_jsonl(funsd_train_path)
    funsd_test = load_jsonl(funsd_test_path)
    synthetic = load_jsonl(synthetic_path)
    in_domain = load_jsonl(in_domain_path)

    print(f"Loaded FUNSD Train: {len(funsd_train)} edges")
    print(f"Loaded FUNSD Test:  {len(funsd_test)} edges")
    print(f"Loaded Synthetic:   {len(synthetic)} edges")
    print(f"Loaded In-Domain:   {len(in_domain)} edges")

    print("\n--- 2. Partitioning Synthetic Dataset (80/10/10 Document-Level Split) ---")
    synth_docs = sorted(list({r["doc_id"] for r in synthetic}))
    num_docs = len(synth_docs)
    n_train = int(num_docs * 0.80)
    n_val = int(num_docs * 0.10)

    train_synth_doc_ids = set(synth_docs[:n_train])
    val_synth_doc_ids = set(synth_docs[n_train:n_train + n_val])
    test_synth_doc_ids = set(synth_docs[n_train + n_val:])

    synth_train = [r for r in synthetic if r["doc_id"] in train_synth_doc_ids]
    synth_val = [r for r in synthetic if r["doc_id"] in val_synth_doc_ids]
    synth_test = [r for r in synthetic if r["doc_id"] in test_synth_doc_ids]

    print(f"Synthetic Docs: {len(train_synth_doc_ids)} train, {len(val_synth_doc_ids)} val, {len(test_synth_doc_ids)} test")
    print(f"Synthetic Edges: {len(synth_train)} train, {len(synth_val)} val, {len(synth_test)} test")

    print("\n--- 3. Assembling Canonical Splits ---")
    # Train: FUNSD train + Synthetic train
    train_split = funsd_train + synth_train
    # Val: FUNSD test + Synthetic val
    val_split = funsd_test + synth_val
    # Test Synthetic
    test_synth_split = synth_test
    # Test In-Domain (Gold Held-Out Benchmark)
    test_indomain_split = in_domain

    splits_dict = {
        "train.jsonl": train_split,
        "val.jsonl": val_split,
        "test_synthetic.jsonl": test_synth_split,
        "test_in_domain.jsonl": test_indomain_split
    }

    for fname, recs in splits_dict.items():
        out_p = os.path.join(splits_dir, fname)
        with open(out_p, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        print(f"Wrote {len(recs)} edges to {out_p}")

    print("\n--- 4. Data-Quality Audit ---")
    # Check 1: Document leakage
    train_docs = {r["doc_id"] for r in train_split}
    val_docs = {r["doc_id"] for r in val_split}
    test_synth_docs = {r["doc_id"] for r in test_synth_split}
    test_indomain_docs = {r["doc_id"] for r in test_indomain_split}

    leakage_train_val = train_docs.intersection(val_docs)
    leakage_train_test = train_docs.intersection(test_synth_docs)
    leakage_train_indomain = train_docs.intersection(test_indomain_docs)

    print(f"Train/Val Document Leakage: {len(leakage_train_val)} (Expected: 0)")
    print(f"Train/Test Synth Leakage:   {len(leakage_train_test)} (Expected: 0)")
    print(f"Train/In-Domain Leakage:    {len(leakage_train_indomain)} (Expected: 0)")
    assert len(leakage_train_val) == 0, "Document leakage detected between Train and Val!"
    assert len(leakage_train_test) == 0, "Document leakage detected between Train and Test Synth!"
    assert len(leakage_train_indomain) == 0, "Document leakage detected between Train and In-Domain!"

    # Check 2: Invalid coordinates & impossible relationships
    all_splits_records = train_split + val_split + test_synth_split + test_indomain_split
    invalid_coords = 0
    self_loops = 0
    invalid_feature_dims = 0

    valid_labels = {"PARENT_OF", "OPTION_OF", "CONTINUATION_OF", "NONE"}
    label_counts_by_source = {}

    for r in all_splits_records:
        src = r["annotation_source"]
        lbl = r["relationship_label"]
        label_counts_by_source.setdefault(src, {}).setdefault(lbl, 0)
        label_counts_by_source[src][lbl] += 1

        sb = r["source_bbox"]
        tb = r["target_bbox"]
        if sb[0] >= sb[2] or sb[1] >= sb[3] or tb[0] >= tb[2] or tb[1] >= tb[3]:
            invalid_coords += 1
        if r["source_block_id"] == r["target_block_id"]:
            self_loops += 1
        feat_vec = r["relative_features"]["feature_vector"]
        if len(feat_vec) != 15:
            invalid_feature_dims += 1

    print(f"Invalid Bounding Boxes:     {invalid_coords}")
    print(f"Self-loop Relationships:    {self_loops}")
    print(f"Invalid Feature Dimensions: {invalid_feature_dims}")

    print("\n--- 5. Class Distributions by Source ---")
    for src, counts in sorted(label_counts_by_source.items()):
        total_s = sum(counts.values())
        print(f"Source '{src}' ({total_s} total edges):")
        for lbl in ["PARENT_OF", "OPTION_OF", "CONTINUATION_OF", "NONE"]:
            c = counts.get(lbl, 0)
            pct = (c / total_s * 100) if total_s > 0 else 0
            print(f"  {lbl:16s}: {c:6d} ({pct:5.1f}%)")

    print("\n--- 6. Class Distributions by Split ---")
    split_stats = {}
    for sname, recs in splits_dict.items():
        sc = {}
        for r in recs:
            l = r["relationship_label"]
            sc[l] = sc.get(l, 0) + 1
        split_stats[sname] = sc
        tot = len(recs)
        print(f"Split '{sname}' ({tot} total edges):")
        for lbl in ["PARENT_OF", "OPTION_OF", "CONTINUATION_OF", "NONE"]:
            c = sc.get(lbl, 0)
            pct = (c / tot * 100) if tot > 0 else 0
            print(f"  {lbl:16s}: {c:6d} ({pct:5.1f}%)")

    # Generate dataset manifest
    manifest = {
        "dataset_name": "SETU-SR",
        "description": "Spatial-Relational Edge Classification Dataset for SETU-NETRA",
        "version": "1.0.0",
        "total_documents": len(train_docs | val_docs | test_synth_docs | test_indomain_docs),
        "total_edges": len(all_splits_records),
        "splits": {
            "train": {
                "file": "splits/train.jsonl",
                "edges_count": len(train_split),
                "distribution": split_stats["train.jsonl"]
            },
            "val": {
                "file": "splits/val.jsonl",
                "edges_count": len(val_split),
                "distribution": split_stats["val.jsonl"]
            },
            "test_synthetic": {
                "file": "splits/test_synthetic.jsonl",
                "edges_count": len(test_synth_split),
                "distribution": split_stats["test_synthetic.jsonl"]
            },
            "test_in_domain": {
                "file": "splits/test_in_domain.jsonl",
                "edges_count": len(test_indomain_split),
                "distribution": split_stats["test_in_domain.jsonl"],
                "note": "Held-out gold evaluation set. Zero leakage into training."
            }
        },
        "quality_audit": {
            "train_val_leakage": len(leakage_train_val),
            "train_test_leakage": len(leakage_train_test),
            "train_indomain_leakage": len(leakage_train_indomain),
            "invalid_coordinates": invalid_coords,
            "self_loops": self_loops,
            "feature_vector_dimension": 15
        }
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest successfully written to {manifest_path}")
    return manifest


if __name__ == "__main__":
    assemble_and_validate_dataset()
