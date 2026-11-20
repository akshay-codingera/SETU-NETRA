import json
import glob
import os
import math
import random
from PIL import Image
from geometry_features import compute_spatial_features

def process_funsd_split(raw_dir, out_jsonl, split_name, seed=42):
    random.seed(seed)
    ann_dir = os.path.join(raw_dir, "annotations")
    img_dir = os.path.join(raw_dir, "images")
    ann_files = sorted(glob.glob(os.path.join(ann_dir, "*.json")))
    
    records = []
    stats = {"PARENT_OF": 0, "OPTION_OF": 0, "CONTINUATION_OF": 0, "NONE": 0}
    
    for fpath in ann_files:
        doc_id = os.path.splitext(os.path.basename(fpath))[0]
        img_path = os.path.join(img_dir, f"{doc_id}.png")
        if os.path.exists(img_path):
            with Image.open(img_path) as im:
                page_w, page_h = im.size
        else:
            page_w, page_h = 1000, 1000  # standard fallback
            
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            
        form = data.get("form", [])
        if not form:
            continue
            
        entities = {}
        for item in form:
            eid = item["id"]
            entities[eid] = {
                "id": eid,
                "text": item.get("text", "").strip(),
                "box": item.get("box", [0, 0, 0, 0]),
                "label": item.get("label", "other"),
                "linking": item.get("linking", [])
            }
            
        # Ground-truth positive links
        pos_links = set()
        for eid, item in entities.items():
            for l in item.get("linking", []):
                if len(l) == 2:
                    src, tgt = l[0], l[1]
                    if src in entities and tgt in entities and src != tgt:
                        pos_links.add((src, tgt))
                        
        # Map positive links to taxonomy
        for src, tgt in pos_links:
            src_ent = entities[src]
            tgt_ent = entities[tgt]
            
            # Semantic mapping rule:
            # Header -> Question: PARENT_OF
            # Question -> Answer: PARENT_OF
            # Header -> Answer/Other: PARENT_OF
            # Question -> Question: PARENT_OF (sub-question)
            # Forms do NOT contain multiple-choice options or multi-passage continuations.
            rel_label = "PARENT_OF"
            
            feats = compute_spatial_features(src_ent["box"], tgt_ent["box"], page_w, page_h)
            record = {
                "doc_id": f"funsd_{doc_id}",
                "page_id": f"funsd_{doc_id}_p1",
                "source_block_id": src,
                "target_block_id": tgt,
                "source_text": src_ent["text"],
                "target_text": tgt_ent["text"],
                "source_role": src_ent["label"].upper(),
                "target_role": tgt_ent["label"].upper(),
                "source_bbox": src_ent["box"],
                "target_bbox": tgt_ent["box"],
                "page_width": page_w,
                "page_height": page_h,
                "relationship_label": rel_label,
                "relative_features": feats,
                "annotation_source": "funsd_entity_linking",
                "confidence": 1.0,
                "provenance": f"FUNSD/{split_name}/annotations/{doc_id}.json"
            }
            records.append(record)
            stats[rel_label] += 1
            
        # Generate informative negative pairs (NONE)
        # For each entity, find close non-linked entities
        num_pos = len(pos_links)
        target_neg = int(num_pos * 1.5)  # balanced 1:1.5 ratio
        neg_candidates = []
        
        all_eids = list(entities.keys())
        for i in range(len(all_eids)):
            for j in range(len(all_eids)):
                if i == j:
                    continue
                eid_i, eid_j = all_eids[i], all_eids[j]
                if (eid_i, eid_j) in pos_links or (eid_j, eid_i) in pos_links:
                    continue
                
                # Check distance
                b_i = entities[eid_i]["box"]
                b_j = entities[eid_j]["box"]
                cx_i = (b_i[0] + b_i[2]) / 2.0
                cy_i = (b_i[1] + b_i[3]) / 2.0
                cx_j = (b_j[0] + b_j[2]) / 2.0
                cy_j = (b_j[1] + b_j[3]) / 2.0
                dist = math.sqrt(((cx_j - cx_i)/page_w)**2 + ((cy_j - cy_i)/page_h)**2)
                
                # Only keep pairs within spatial radius 0.40 (informative negatives)
                if dist < 0.40:
                    neg_candidates.append((dist, eid_i, eid_j))
                    
        # Sort by distance (harder negatives first) and sample
        neg_candidates.sort(key=lambda x: x[0])
        sampled_neg = neg_candidates[:target_neg]
        
        for dist, src, tgt in sampled_neg:
            src_ent = entities[src]
            tgt_ent = entities[tgt]
            feats = compute_spatial_features(src_ent["box"], tgt_ent["box"], page_w, page_h)
            record = {
                "doc_id": f"funsd_{doc_id}",
                "page_id": f"funsd_{doc_id}_p1",
                "source_block_id": src,
                "target_block_id": tgt,
                "source_text": src_ent["text"],
                "target_text": tgt_ent["text"],
                "source_role": src_ent["label"].upper(),
                "target_role": tgt_ent["label"].upper(),
                "source_bbox": src_ent["box"],
                "target_bbox": tgt_ent["box"],
                "page_width": page_w,
                "page_height": page_h,
                "relationship_label": "NONE",
                "relative_features": feats,
                "annotation_source": "funsd_hard_negative",
                "confidence": 1.0,
                "provenance": f"FUNSD/{split_name}/annotations/{doc_id}.json"
            }
            records.append(record)
            stats["NONE"] += 1
            
    # Write to JSONL
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as out_fp:
        for r in records:
            out_fp.write(json.dumps(r) + "\n")
            
    print(f"[{split_name.upper()}] Processed {len(ann_files)} documents -> {len(records)} edge records written to {out_jsonl}")
    print(f"  Distribution: {stats}")
    return records, stats

if __name__ == "__main__":
    train_dir = "training/datasets/SETU-SR/FUNSD/raw/dataset/training_data"
    test_dir = "training/datasets/SETU-SR/FUNSD/raw/dataset/testing_data"
    
    out_train = "training/datasets/SETU-SR/FUNSD/funsd_edges_train.jsonl"
    out_test = "training/datasets/SETU-SR/FUNSD/funsd_edges_test.jsonl"
    
    process_funsd_split(train_dir, out_train, "training_data", seed=42)
    process_funsd_split(test_dir, out_test, "testing_data", seed=1337)
