"""
factory.py: Factory for instantiating and diagnosing semantic embedding backends.

Why this file exists:
Provides explicit, reproducible backend selection across:
- 'offline': Fast, deterministic 512-dim subword feature-hashing baseline (zero neural downloads).
- 'neural': Genuine 384-dim pretrained SentenceTransformer ('all-MiniLM-L6-v2'); fails clearly if unavailable.
- 'auto': Intelligently selects 'neural' if weights are locally cached, otherwise falls back to 'offline'.
"""

from typing import Dict, Optional, Tuple
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine


def get_available_backends() -> Dict[str, bool]:
    """Check availability status of all supported embedding backends."""
    neural_eng = NeuralSentenceEmbeddingEngine()
    return {
        "offline": True,
        "neural": neural_eng.is_available(),
    }


def get_embedding_engine(engine_name: str = "auto") -> BaseEmbeddingEngine:
    """Retrieve an embedding engine instance based on configuration and local availability.

    Args:
        engine_name: 'auto', 'offline', 'neural' (or aliases 'minilm', 'tfidf').

    Returns:
        An instance of BaseEmbeddingEngine.

    Raises:
        RuntimeError: If 'neural' backend was explicitly requested but model weights/dependencies
                      are not locally available (strictly prevents silent substitution).
        ValueError: If an unrecognized engine name is passed.
    """
    normalized = engine_name.lower().strip()

    if normalized in ("offline", "offline_semantic_tfidf", "tfidf"):
        return OfflineSemanticEngine()

    if normalized in ("neural", "minilm", "transformer"):
        engine = NeuralSentenceEmbeddingEngine()
        if not engine.is_available():
            raise RuntimeError(
                f"Neural backend '{normalized}' was explicitly requested, but weights or "
                f"dependencies are not available locally ({engine._load_error}).\n"
                "To resolve, run: python scripts/download_semantic_model.py\n"
                "Or switch to the offline baseline with: --semantic-engine offline"
            )
        return engine

    if normalized == "auto":
        neural = NeuralSentenceEmbeddingEngine()
        if neural.is_available():
            return neural
        return OfflineSemanticEngine()

    raise ValueError(
        f"Unknown embedding engine name: '{engine_name}'. "
        "Supported choices: 'auto', 'offline', 'neural'."
    )
