import json, glob, os
from PIL import Image

def analyze_funsd(split_dir):
    ann_files = glob.glob(os.path.join(split_dir, "annotations", "*.json"))
    link_types = {}
    total_entities = 0
    total_links = 0
    unique_links = set()
    
    for fpath in ann_files:
        doc_id = os.path.splitext(os.path.basename(fpath))[0]
        with open(fpath, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        form = data.get('form', [])
        total_entities += len(form)
        id_to_label = {item['id']: item['label'] for item in form}
        
        for item in form:
            for l in item.get('linking', []):
                if len(l) == 2:
                    src, tgt = l[0], l[1]
                    link_key = (doc_id, src, tgt)
                    if link_key not in unique_links:
                        unique_links.add(link_key)
                        src_label = id_to_label.get(src, 'unknown')
                        tgt_label = id_to_label.get(tgt, 'unknown')
                        pair_type = f"{src_label} -> {tgt_label}"
                        link_types[pair_type] = link_types.get(pair_type, 0) + 1
                        total_links += 1
                        
    print(f"Split {split_dir}: {len(ann_files)} documents, {total_entities} entities, {total_links} unique directed links")
    for pt, cnt in sorted(link_types.items(), key=lambda x: -x[1]):
        print(f"  {pt}: {cnt}")

analyze_funsd("training/datasets/SETU-SR/FUNSD/raw/dataset/training_data")
analyze_funsd("training/datasets/SETU-SR/FUNSD/raw/dataset/testing_data")
