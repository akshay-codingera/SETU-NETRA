"""
neural_engine.py: Pretrained Transformer sentence embedding engine adapter for SETU-NETRA.

Why this file exists:
Provides a real pretrained sentence-embedding backend ('all-MiniLM-L6-v2') for semantic similarity,
open-vocabulary domain ranking, and paraphrase matching. Adheres to strict constraints:
- Uses actual pretrained model weights and inference implementation.
- Never downloads weights automatically during ordinary execution or unit testing.
- Caches the loaded model instance in memory for fast CPU reuse.
- Provides clear diagnostic errors when model weights are not locally cached.
"""

from typing import Any, Dict, Optional, Sequence
import numpy as np
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine


class NeuralSentenceEmbeddingEngine(BaseEmbeddingEngine):
    """Real pretrained sentence transformer engine using all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", local_files_only: bool = True):
        self._model_name = model_name
        self._local_files_only = local_files_only
        self._model = None
        self._dimension = 384
        self._load_error: Optional[str] = None
        self._tried_loading = False

    @property
    def engine_name(self) -> str:
        return f"neural_{self._model_name}"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_metadata(self) -> Dict[str, Any]:
        """Diagnostic metadata describing the pretrained model and its resource profile."""
        return {
            "model_identifier": self._model_name,
            "source": f"sentence-transformers/{self._model_name}",
            "architecture": "MiniLM (6-layer, 384-hidden, 12-heads)",
            "license": "Apache-2.0",
            "parameters": 22_713_216,
            "embedding_dimension": self._dimension,
            "max_sequence_length": 256,
            "storage_footprint_mb": 90.0,
            "target_hardware": "CPU (Intel Core i5, 16 GB RAM)",
            "is_cached_locally": self.is_available(),
        }

    def is_available(self) -> bool:
        """Check whether sentence_transformers is installed and model weights are cached locally."""
        if self._model is not None:
            return True
        if self._tried_loading and self._load_error is not None:
            return False

        self._tried_loading = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            # Strictly require local files only to avoid accidental network downloads during execution
            self._model = SentenceTransformer(self._model_name, local_files_only=self._local_files_only)
            
            # Use modern get_embedding_dimension() with backward-compatible fallback
            if hasattr(self._model, "get_embedding_dimension"):
                self._dimension = self._model.get_embedding_dimension()
            elif hasattr(self._model, "get_sentence_embedding_dimension"):
                self._dimension = self._model.get_sentence_embedding_dimension()
            else:
                self._dimension = 384

            self._load_error = None
            return True
        except Exception as err:
            self._load_error = str(err)
            self._model = None
            return False

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Compute genuine normalized dense embeddings using the pretrained neural model.

        Args:
            texts: Sequence of strings to embed.

        Returns:
            2D numpy array of shape (len(texts), 384) with L2-normalized rows.

        Raises:
            RuntimeError: If model weights are not locally cached or dependencies are missing.
        """
        if not self.is_available():
            raise RuntimeError(
                f"Neural embedding engine '{self._model_name}' is not locally available. "
                f"Details: {self._load_error}\n"
                "To resolve this, ensure dependencies are installed:\n"
                "  python -m pip install sentence-transformers\n"
                "and explicitly download and cache the model weights using:\n"
                "  python scripts/download_semantic_model.py\n"
                "Alternatively, run with '--semantic-engine offline' to use the dependency-free baseline."
            )

        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)

        # Batch inference using the loaded model
        raw_embeddings = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return raw_embeddings.astype(np.float32)
