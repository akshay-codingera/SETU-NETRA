import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path("src").resolve()))

from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.semantic.domain.taxonomy import DomainTaxonomy
from setu_netra.semantic.domain.classifier import OpenVocabularyDomainClassifier

tax = DomainTaxonomy()
dev_cases = json.load(open("sample_data/development_calibration_dataset.json", encoding="utf-8"))

for name, eng in [("offline", OfflineSemanticEngine()), ("neural", NeuralSentenceEmbeddingEngine())]:
    # Use appropriate provisional threshold
    abstain_thresh = 0.28 if name == "offline" else 0.22
    clf = OpenVocabularyDomainClassifier(
        embedding_engine=eng,
        taxonomy=tax,
        abstention_threshold=abstain_thresh,
    )
    print(f"\n=======================================================")
    print(f"=== Backend: {name} (dim={eng.dimension}, thresh={abstain_thresh}) ===")
    print(f"=======================================================")
    correct = 0
    total = len(dev_cases)
    for c in dev_cases:
        candidates, status, warnings = clf.classify(c["text"])
        is_abs = c["is_abstention"]
        if is_abs:
            pred_ok = (status in ("UNKNOWN_DOMAIN", "INSUFFICIENT_EVIDENCE"))
            pred_name = f"ABSTAIN ({status})"
            top_score = candidates[0].similarity_score if candidates else 0.0
        else:
            top_cand = candidates[0] if candidates else None
            top_score = top_cand.similarity_score if top_cand else 0.0
            pred_name = top_cand.domain_name if top_cand else "NONE"
            pred_ok = (pred_name == c["expected_domain"] and status in ("CLASSIFIED", "MULTI_LABEL"))

        if pred_ok:
            correct += 1
        mark = "PASS" if pred_ok else "FAIL"
        print(f"[{c['id']}] {mark}: score={top_score:.4f} -> {pred_name[:32]} (Exp: {c['expected_domain'][:25]})")
    acc = (correct / total) * 100.0
    print(f"\nAccuracy on Dev Set: {correct}/{total} ({acc:.1f}%)")
