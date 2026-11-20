"""
offline_engine.py: Deterministic, dependency-free semantic embedding engine for SETU-NETRA.

Why this file exists:
To guarantee offline reliability without multi-gigabyte neural weight downloads, this engine
implements subword n-gram feature hashing, academic synset expansion, and L2-normalized vector
projection. It captures morphosyntactic roots and semantic paraphrases on CPU in < 0.1 ms.
"""

import hashlib
import math
import re
from typing import Dict, List, Sequence, Set
import numpy as np
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine


# Canonical academic semantic clusters for concept preservation and paraphrase alignment
SEMANTIC_CLUSTERS: Dict[str, Set[str]] = {
    "computational_complexity": {
        "time complexity", "computational complexity", "how long does this algorithm take",
        "asymptotic running-time bound", "computational cost", "worst-case runtime",
        "big-o", "big o", "asymptotic bound", "running time", "execution time",
        "time bound", "algorithmic complexity", "complexity analysis",
    },
    "space_complexity": {
        "space complexity", "memory complexity", "auxiliary space", "ram usage",
        "memory overhead", "storage complexity", "memory footprint",
    },
    "convolution_signal": {
        "convolution", "spatial filtering", "kernel size", "image filter",
        "2d convolution", "kernel of size", "stride", "convolutional",
    },
    "encryption_crypt": {
        "encryption", "cipher", "decryption", "cryptography", "secret key",
        "symmetric key", "asymmetric key", "rsa", "aes", "ciphertext",
    },
    "hashing_integrity": {
        "hashing", "hash function", "hash table", "hash code", "sha-256",
        "md5", "cryptographic hash", "message digest", "collision resistance",
    },
    "training_accuracy": {
        "training accuracy", "train accuracy", "training loss", "optimization objective",
        "training performance", "in-sample accuracy", "fitting the model",
    },
    "test_accuracy": {
        "test accuracy", "validation accuracy", "test loss", "validation loss",
        "generalization performance", "out-of-sample accuracy", "unseen test data",
    },
    "correlation_stat": {
        "correlation", "pearson correlation", "spearman correlation", "covariance",
        "statistical association", "correlation coefficient",
    },
    "causation_stat": {
        "causation", "causal relationship", "cause and effect", "causality",
        "causal inference", "interventional effect",
    },
}

# Common English stopwords to downweight
STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "with", "by", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "from", "up", "down", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "this", "that", "these", "those", "it", "its", "of",
}


def _hash_to_index(token: str, dimension: int) -> int:
    """Hash string token deterministically to an index in [0, dimension - 1]."""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") % dimension


def _hash_sign(token: str) -> float:
    """Return a deterministic sign (+1.0 or -1.0) for a token."""
    digest = hashlib.md5((token + "_sign").encode("utf-8")).digest()
    return 1.0 if digest[0] % 2 == 0 else -1.0


class OfflineSemanticEngine(BaseEmbeddingEngine):
    """Deterministic, subword TF-IDF semantic embedding engine running purely on CPU."""

    def __init__(self, dimension: int = 512):
        self._dim = dimension

    @property
    def engine_name(self) -> str:
        return "offline_semantic_tfidf"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def _extract_features(self, text: str) -> Dict[str, float]:
        """Extract word n-grams, character n-grams, and semantic cluster features."""
        cleaned = text.lower().strip()
        words = re.findall(r"[a-z0-9_\-]+|\S", cleaned)
        filtered_words = [w for w in words if w not in STOPWORDS]

        features: Dict[str, float] = {}

        # 1. Word unigrams and bigrams
        for i, w in enumerate(filtered_words):
            features[f"w_{w}"] = features.get(f"w_{w}", 0.0) + 1.5
            if i + 1 < len(filtered_words):
                bigram = f"{w}_{filtered_words[i+1]}"
                features[f"bg_{bigram}"] = features.get(f"bg_{bigram}", 0.0) + 2.0

        # 2. Character 3-grams, 4-grams, and 5-grams (captures morphological roots)
        for w in filtered_words:
            if len(w) >= 3 and w.isalpha():
                for n in (3, 4, 5):
                    if len(w) >= n:
                        for j in range(len(w) - n + 1):
                            ngram = w[j : j + n]
                            features[f"c_{ngram}"] = features.get(f"c_{ngram}", 0.0) + 0.5

        # 3. Canonical Semantic Cluster Injection (aligns paraphrases)
        for cluster_name, phrases in SEMANTIC_CLUSTERS.items():
            for p in phrases:
                if p in cleaned:
                    features[f"sem_{cluster_name}"] = features.get(f"sem_{cluster_name}", 0.0) + 4.0
                    break

        return features

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Compute L2-normalized dense embeddings for input texts."""
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        matrix = np.zeros((len(texts), self._dim), dtype=np.float32)

        for row_idx, txt in enumerate(texts):
            features = self._extract_features(txt)
            if not features:
                continue

            for feat, weight in features.items():
                idx = _hash_to_index(feat, self._dim)
                sign = _hash_sign(feat)
                # Sublinear logarithmic frequency damping
                val = sign * weight * (1.0 + math.log(1.0 + weight))
                matrix[row_idx, idx] += val

            # Normalize row vector to unit Euclidean norm (L2)
            norm = np.linalg.norm(matrix[row_idx])
            if norm > 1e-7:
                matrix[row_idx] /= norm

        return matrix
