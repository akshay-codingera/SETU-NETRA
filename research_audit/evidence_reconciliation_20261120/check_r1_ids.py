import json, os

splits_dir = "training/datasets/SETU-SR/splits"
files = ["train.jsonl", "val.jsonl", "test_synthetic.jsonl", "test_in_domain.jsonl"]

total_unique_docs = set()
total_unique_pages = set()

for fname in files:
    p = os.path.join(splits_dir, fname)
    docs = set()
    pages = set()
    sources = set()
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            d_id = rec.get("doc_id")
            p_id = rec.get("page_id")
            src = rec.get("annotation_source")
            docs.add(d_id)
            pages.add(p_id)
            total_unique_docs.add(d_id)
            total_unique_pages.add(p_id)
            sources.add(src)
    print(f"File: {fname:22s} | Unique doc_ids: {len(docs):3d} | Unique page_ids: {len(pages):3d} | Annotation sources: {sources}")

print("-" * 60)
print(f"Total Unique doc_ids across ALL splits: {len(total_unique_docs)}")
print(f"Total Unique page_ids across ALL splits: {len(total_unique_pages)}")
