"""
classifier.py: Open-vocabulary hybrid domain classifier for academic & scientific text.

Why this file exists:
Classifies document text into hierarchical and multi-label scientific domains by
comparing semantic embeddings against natural-language domain descriptions. It supports
unfamiliar terminology, interdisciplinary overlap, contextual sense disambiguation,
and explicit abstention when evidence is insufficient.

Key Architecture:
- Supports both 512-dim offline hashing and 384-dim pretrained neural embeddings without dimension manipulation.
- Caches domain-description embeddings in memory and invalidates/rebuilds them upon backend or taxonomy changes.
- Engine-calibrated provisional abstention thresholds (0.28 for offline, 0.22 for neural).
- Note: Cosine similarity scores indicate directional semantic alignment, not calibrated probabilities.
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
from setu_netra.core.contracts import DisambiguationDetail, DomainCandidate
from setu_netra.semantic.domain.taxonomy import DEFAULT_DOMAINS, DomainDefinition, DomainTaxonomy
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine


# Mapping from disambiguated senses to primary academic domain names
SENSE_TO_DOMAIN_NAME: Dict[str, str] = {
    "Image Processing / Spatial Convolution": "Signal & Digital Image Processing",
    "Operating Systems / System Architecture": "Operating Systems & Computer Architecture",
    "Machine Learning / Support Vector Machines": "Artificial Intelligence & Machine Learning",
    "Linear Algebra & Group Theory": "Linear Algebra",
    "Machine Learning / Statistical Predictor": "Artificial Intelligence & Machine Learning",
    "Relational Database Schema": "Database Systems",
    "Database Systems (Normal Forms)": "Database Systems",
    "Machine Learning / Feature Preprocessing": "Artificial Intelligence & Machine Learning",
    "Statistics & Machine Learning": "Probability & Statistics",
    "Cellular Biology": "Cellular Biology & Genetics",
}


class OpenVocabularyDomainClassifier:
    """Hybrid domain classifier using semantic vector ranking, description caching, and sense grounding."""

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        taxonomy: Optional[DomainTaxonomy] = None,
        abstention_threshold: Optional[float] = None,
        multi_label_threshold: Optional[float] = None,
        top_k: int = 4,
    ):
        self._engine = embedding_engine
        self._taxonomy = taxonomy or DomainTaxonomy()
        self._top_k = top_k

        # Provisional engine-aware threshold calibration
        # Note: Dense neural representations have a different cosine similarity distribution than subword hash vectors.
        is_neural = "neural" in self._engine.engine_name
        self._abstention_threshold = (
            abstention_threshold if abstention_threshold is not None
            else (0.22 if is_neural else 0.28)
        )
        self._multi_label_threshold = (
            multi_label_threshold if multi_label_threshold is not None
            else (0.32 if is_neural else 0.38)
        )

        # In-memory domain description vector cache
        self._domain_list: List[DomainDefinition] = []
        self._domain_ids: List[str] = []
        self._domain_texts: List[str] = []
        self._cached_domain_vectors: np.ndarray = np.zeros((0, self._engine.dimension), dtype=np.float32)
        self._cache_key: Optional[Tuple[str, int, int]] = None

        self._build_domain_cache()

    @property
    def embedding_engine(self) -> BaseEmbeddingEngine:
        return self._engine

    @property
    def abstention_threshold(self) -> float:
        return self._abstention_threshold

    @property
    def multi_label_threshold(self) -> float:
        return self._multi_label_threshold

    @property
    def cached_vectors_shape(self) -> Tuple[int, int]:
        return self._cached_domain_vectors.shape

    def _build_domain_cache(self) -> None:
        """Embed and cache domain descriptions in memory."""
        self._domain_list = self._taxonomy.list_domains()
        self._domain_ids = [d.domain_id for d in self._domain_list]
        self._domain_texts = [f"{d.domain_name}. {d.description}" for d in self._domain_list]
        self._cached_domain_vectors = self._engine.embed_texts(self._domain_texts)
        self._cache_key = (
            self._engine.engine_name,
            self._engine.dimension,
            len(self._domain_list),
        )

    def refresh_cache(self) -> None:
        """Invalidate and rebuild domain vectors cache."""
        self._build_domain_cache()

    def set_embedding_engine(self, engine: BaseEmbeddingEngine) -> None:
        """Switch embedding engine and immediately rebuild vector cache to maintain dimension compatibility."""
        self._engine = engine
        is_neural = "neural" in self._engine.engine_name
        self._abstention_threshold = 0.22 if is_neural else 0.28
        self._multi_label_threshold = 0.32 if is_neural else 0.38
        self._build_domain_cache()

    def classify(
        self,
        text: str,
        context_text: str = "",
        disambiguations: Optional[Sequence[DisambiguationDetail]] = None,
    ) -> Tuple[List[DomainCandidate], str, List[str]]:
        """Classify input text into ranked academic/scientific domains.

        Args:
            text: Primary text being analyzed.
            context_text: Optional document context.
            disambiguations: Optional polysemy disambiguation records.

        Returns:
            (ranked_candidates, status, warnings)
            status is one of: 'CLASSIFIED', 'MULTI_LABEL', 'INSUFFICIENT_EVIDENCE', 'UNKNOWN_DOMAIN'
        """
        warnings: List[str] = []
        cleaned = text.strip()
        if not cleaned:
            return [], "INSUFFICIENT_EVIDENCE", ["Empty input text provided for domain classification."]

        # Ensure cache is valid for current engine & taxonomy
        current_key = (
            self._engine.engine_name,
            self._engine.dimension,
            len(self._taxonomy.list_domains()),
        )
        if self._cache_key != current_key or len(self._cached_domain_vectors) == 0:
            self._build_domain_cache()

        if len(self._cached_domain_vectors) == 0:
            return [], "INSUFFICIENT_EVIDENCE", ["Domain taxonomy contains no registered domains."]

        # Combine text with contextual cue snippet
        full_query = f"{cleaned} {context_text[:200]}".strip() if context_text else cleaned
        query_vec = self._engine.embed_texts([full_query])

        # Dimension safety assertion (guarantees no silent truncation/padding)
        if query_vec.shape[1] != self._cached_domain_vectors.shape[1]:
            # Force cache rebuild if dimension mismatch occurs
            self._build_domain_cache()

        # Compute cosine similarity across all cached domain descriptions (shape: (num_domains,))
        dense_similarities = np.matmul(query_vec, self._cached_domain_vectors.T)[0]
        max_dense = float(np.max(dense_similarities)) if len(dense_similarities) > 0 else 1.0

        lower_query = full_query.lower()
        # Clean broken OCR word fragments for robust matching
        normalized_query = re.sub(r"\b([a-z]{1,2})\s+([a-z]{3,})\b", r"\1\2", lower_query)

        # Check for disambiguated sense targets
        disambiguated_target_domains: Dict[str, str] = {}
        if disambiguations:
            for dis in disambiguations:
                if dis.confidence >= 0.60 and "AMBIGUOUS" not in dis.resolved_sense:
                    target_dom = SENSE_TO_DOMAIN_NAME.get(dis.resolved_sense)
                    if target_dom:
                        disambiguated_target_domains[target_dom] = (
                            f"Disambiguated '{dis.term}' -> {dis.resolved_sense}"
                        )

        # Compute hybrid score combining dense similarity with representative concept grounding
        scored_candidates: List[Tuple[int, float, Tuple[str, ...]]] = []

        for idx, domain_def in enumerate(self._domain_list):
            raw_dense = float(dense_similarities[idx])
            matched_evidence: List[str] = []

            # 1. Add disambiguation evidence if applicable
            if domain_def.domain_name in disambiguated_target_domains:
                matched_evidence.append(disambiguated_target_domains[domain_def.domain_name])

            # 2. Check concept overlap using full phrase or morphological root (length >= 4)
            for concept in domain_def.representative_concepts:
                c_low = concept.lower()
                if c_low in lower_query or c_low in normalized_query:
                    matched_evidence.append(concept)
                else:
                    # Multi-word concepts: require all constituent word stems to match
                    c_parts = [p for p in c_low.split() if len(p) >= 4]
                    if len(c_parts) >= 2 and all(p[:4] in normalized_query for p in c_parts):
                        matched_evidence.append(concept)

            if matched_evidence:
                concept_weight = min(1.0, 0.40 + 0.25 * len(matched_evidence))
                dense_norm = max(0.0, raw_dense / max(1e-4, max_dense))
                calibrated = min(1.0, 0.45 * dense_norm + 0.55 * concept_weight)
            else:
                calibrated = raw_dense

            scored_candidates.append((idx, calibrated, tuple(matched_evidence)))

        # Sort descending by calibrated score
        scored_candidates.sort(key=lambda it: it[1], reverse=True)
        top_score = scored_candidates[0][1] if scored_candidates else 0.0

        # Open-set & Unknown handling: Abstain when score is below calibrated threshold
        if top_score < self._abstention_threshold:
            status = "UNKNOWN_DOMAIN" if top_score < 0.18 else "INSUFFICIENT_EVIDENCE"
            warnings.append(
                f"Domain alignment score {top_score:.3f} is below provisional abstention threshold {self._abstention_threshold:.2f}."
            )
            uncalibrated = [
                DomainCandidate(
                    domain_id=self._domain_list[idx].domain_id,
                    domain_name=self._domain_list[idx].domain_name,
                    hierarchy_path=self._domain_list[idx].hierarchy_path,
                    similarity_score=round(score, 4),
                    is_primary=False,
                    evidence_terms=(),
                )
                for idx, score, _ in scored_candidates[:2]
            ]
            return uncalibrated, status, warnings

        # Build active candidates list
        candidates: List[DomainCandidate] = []
        for rank, (idx, score, evidence) in enumerate(scored_candidates[: self._top_k]):
            domain_def = self._domain_list[idx]
            is_primary = (rank == 0)

            # Keep secondary domains if score exceeds multi-label threshold and is close to top
            if is_primary or (score >= self._multi_label_threshold and (top_score - score) <= 0.25):
                candidates.append(
                    DomainCandidate(
                        domain_id=domain_def.domain_id,
                        domain_name=domain_def.domain_name,
                        hierarchy_path=domain_def.hierarchy_path,
                        similarity_score=round(score, 4),
                        is_primary=is_primary,
                        evidence_terms=evidence,
                    )
                )

        status = "MULTI_LABEL" if len(candidates) > 1 else "CLASSIFIED"
        return candidates, status, warnings
