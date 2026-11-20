"""
Embedding engines package for SETU-NETRA.
"""

from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine

__all__ = [
    "BaseEmbeddingEngine",
    "OfflineSemanticEngine",
    "NeuralSentenceEmbeddingEngine",
    "get_embedding_engine",
]
