"""
base.py: Abstract base class for semantic embedding engines in SETU-NETRA.

Why this file exists:
Semantic similarity, paraphrase matching, and open-vocabulary domain classification
require dense vector representations of text. Decoupling the embedding interface
allows seamless switching between lightweight offline subword vectorizers and
pretrained neural models (e.g. MiniLM) without modifying downstream classification logic.
"""

from abc import ABC, abstractmethod
from typing import List, Sequence
import numpy as np


class BaseEmbeddingEngine(ABC):
    """Abstract interface for sentence embedding engines."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Identifying name of the active embedding engine."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the output embedding vectors."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the engine dependencies and weights are locally available."""
        pass

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Compute L2-normalized dense embeddings for a sequence of texts.

        Args:
            texts: Sequence of input text strings.

        Returns:
            2D numpy float32 array of shape (len(texts), dimension) where each
            row has unit Euclidean norm (||v||_2 = 1.0).
        """
        pass

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two text strings in range [0.0, 1.0]."""
        if not text_a.strip() or not text_b.strip():
            return 0.0

        vecs = self.embed_texts([text_a, text_b])
        dot = float(np.dot(vecs[0], vecs[1]))
        return max(0.0, min(1.0, dot))

    def batch_similarity(self, queries: Sequence[str], candidates: Sequence[str]) -> np.ndarray:
        """Compute pairwise cosine similarity matrix between queries and candidates.

        Returns:
            2D numpy float32 array of shape (len(queries), len(candidates)).
        """
        if not queries or not candidates:
            return np.zeros((len(queries), len(candidates)), dtype=np.float32)

        q_vecs = self.embed_texts(queries)
        c_vecs = self.embed_texts(candidates)
        # Cosine similarity is matrix dot product of unit-norm vectors
        sim_matrix = np.matmul(q_vecs, c_vecs.T)
        return np.clip(sim_matrix, 0.0, 1.0)
