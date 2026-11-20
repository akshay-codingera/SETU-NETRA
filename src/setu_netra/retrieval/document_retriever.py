"""
document_retriever.py: Evidence-grounded semantic and lexical document retriever for SETU-NETRA.

Why this file exists:
Replaces hardcoded static reference tuples with genuine retrieval over the organization's
persisted document repository. Combines dense semantic vector search with lexical term
matching, guaranteeing that every retrieved passage traces back to exact spatial bounding-box
coordinates and page numbers.

Milestone 6 Sprint 1 Upgrades:
- Defensive dense cosine score rectification (prevents negative semantic scores from dragging
  down strong lexical keyword matches).
- Fully independent and configurable dense-only, lexical-only, and hybrid scoring.
- Near-duplicate passage and repeated header suppression in ranked results.
"""

import difflib
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import numpy as np

from setu_netra.core.contracts import RetrievedPassage
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore

logger = logging.getLogger(__name__)


def tokenize_text(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric terms for lexical matching."""
    return set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower()))


def rectify_dense_score(raw_score: float, method: str = "rectify") -> float:
    """Transform raw cosine similarity into a bounded, non-negative semantic score in [0.0, 1.0].

    Mathematical Justification:
    In unit-normalized sentence embedding spaces (e.g. 384-dim MiniLM), cosine similarity
    theoretically ranges in [-1.0, 1.0]. On natural language corpora, unrelated passages
    cluster near 0.0 or slightly negative (-0.1 to -0.01). A negative cosine indicates
    directional dissimilarity or orthogonality; it does NOT represent affirmative evidence of
    contradiction that should penalize exact keyword matches.

    Rectification (ReLU / non-negative clipping):
        S_rect = max(0.0, min(1.0, S_raw))

    Properties:
    1. For S_raw >= 0.0, exact linear order and relative differences are strictly preserved.
    2. For S_raw < 0.0, the score is bounded at 0.0 (zero semantic evidence), preventing
       negative scores from dragging down legitimate lexical matches in hybrid combination.
    3. Guarantees S_rect in [0.0, 1.0], making it mathematically commensurate with lexical scores.

    Args:
        raw_score: Raw dot product / cosine similarity.
        method: Transformation method ('rectify' or 'none').

    Returns:
        Transformed dense score in [0.0, 1.0] (or raw float if method='none').
    """
    if method == "rectify":
        return max(0.0, min(1.0, float(raw_score)))
    return float(raw_score)


def compute_lexical_similarity(query_tokens: Set[str], block_tokens: Set[str]) -> float:
    """Compute normalized cosine coefficient of lexical term overlap in [0.0, 1.0].

    Formula:
        S_lex = |Q intersect B| / sqrt(|Q| * |B|)
    """
    if not query_tokens or not block_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(block_tokens))
    denom = (len(query_tokens) * len(block_tokens)) ** 0.5
    return float(overlap / denom) if denom > 0 else 0.0


def compute_hybrid_score(
    dense_score: float,
    lexical_score: float,
    alpha: float = 0.70,
    normalize_dense: bool = True,
) -> Tuple[float, float]:
    """Compute combined hybrid relevance score in [0.0, 1.0].

    Formula:
        S_hybrid = alpha * S_dense_norm + (1 - alpha) * S_lexical

    Args:
        dense_score: Raw or normalized dense score.
        lexical_score: Lexical term overlap score in [0.0, 1.0].
        alpha: Weight for dense vs lexical (0.0 = pure lexical, 1.0 = pure dense).
        normalize_dense: Whether to apply non-negative rectification to dense score.

    Returns:
        Tuple of (hybrid_score, normalized_dense_score).
    """
    norm_dense = rectify_dense_score(dense_score) if normalize_dense else float(dense_score)
    clamped_lex = max(0.0, min(1.0, float(lexical_score)))
    clamped_alpha = max(0.0, min(1.0, float(alpha)))
    hybrid = clamped_alpha * norm_dense + (1.0 - clamped_alpha) * clamped_lex
    return float(hybrid), float(norm_dense)


def compute_bm25_scores(
    query_tokens: Sequence[str],
    corpus_tokens: Sequence[Sequence[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    """Compute Okapi BM25 relevance scores for a query across a corpus of tokenized blocks.

    Formula:
        BM25(D, Q) = sum_{q in Q} IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl)))
        IDF(q) = ln(1 + (N - df(q) + 0.5) / (df(q) + 0.5))
    """
    N = len(corpus_tokens)
    if N == 0 or not query_tokens:
        return [0.0] * N

    doc_lengths = [len(doc) for doc in corpus_tokens]
    avgdl = sum(doc_lengths) / N if N > 0 else 1.0

    q_unique = set(query_tokens)
    df: Dict[str, int] = {}
    for term in q_unique:
        df[term] = sum(1 for doc in corpus_tokens if term in doc)

    idf: Dict[str, float] = {}
    for term in q_unique:
        n_q = df[term]
        idf[term] = float(np.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5)))

    raw_scores: List[float] = []
    for doc_idx, doc in enumerate(corpus_tokens):
        dl = doc_lengths[doc_idx]
        denom_norm = k1 * (1.0 - b + b * (dl / (avgdl or 1.0)))

        tf_dict: Dict[str, int] = {}
        for token in doc:
            if token in q_unique:
                tf_dict[token] = tf_dict.get(token, 0) + 1

        score = 0.0
        for term in q_unique:
            tf = tf_dict.get(term, 0)
            if tf > 0:
                tf_term = (tf * (k1 + 1.0)) / (tf + denom_norm)
                score += idf[term] * tf_term
        raw_scores.append(float(score))

    max_s = max(raw_scores) if raw_scores else 0.0
    if max_s > 0.0:
        return [round(float(s / max_s), 4) for s in raw_scores]
    return raw_scores


def reciprocal_rank_fusion(
    ranked_indices_lists: Sequence[List[int]],
    weights: Optional[Sequence[float]] = None,
    k: int = 60,
) -> Dict[int, float]:
    """Compute Reciprocal Rank Fusion (RRF) scores over ranked candidate lists.

    Formula:
        RRF(d) = sum_{m in M} w_m / (k + rank_m(d))
    """
    rrf_scores: Dict[int, float] = {}
    if not ranked_indices_lists:
        return rrf_scores

    eff_weights = weights or ([1.0] * len(ranked_indices_lists))
    for list_idx, ranked_list in enumerate(ranked_indices_lists):
        w = eff_weights[list_idx]
        for rank, candidate_idx in enumerate(ranked_list):
            rrf_scores[candidate_idx] = rrf_scores.get(candidate_idx, 0.0) + (w / (k + (rank + 1)))

    return rrf_scores


def compute_text_similarity(text1: str, text2: str) -> float:
    """Compute normalized text similarity in [0.0, 1.0] for duplicate passage suppression.

    Combines token Jaccard screening with character SequenceMatcher ratio.
    Detects exact duplicates (1.0), repeated headers across pages (>= 0.85),
    and minor typographical variations (>= 0.85), while distinguishing separate
    questions that share common question phrasing (< 0.75).
    """
    s1 = " ".join(text1.lower().split())
    s2 = " ".join(text2.lower().split())
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Token-level alphanumeric set
    tokens1 = set(re.findall(r"\b\w+\b", s1))
    tokens2 = set(re.findall(r"\b\w+\b", s2))
    if not tokens1 or not tokens2:
        return 0.0

    jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
    # Fast exit for largely disjoint texts
    if jaccard < 0.35:
        return float(jaccard)

    # For overlapping texts, compute character sequence alignment and blend
    seq_ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    return float(0.40 * jaccard + 0.60 * seq_ratio)


class DocumentRetriever:
    """Hybrid semantic and lexical retriever grounded in the persistent document store."""

    def __init__(
        self,
        store: SQLiteDocumentStore,
        embedding_engine: BaseEmbeddingEngine,
        default_alpha: float = 0.70,
        default_threshold: float = 0.20,
        duplicate_threshold: float = 0.85,
        enable_duplicate_suppression: bool = True,
    ):
        self.store = store
        self.embedding_engine = embedding_engine
        self.default_alpha = default_alpha
        self.default_threshold = default_threshold
        self.duplicate_threshold = duplicate_threshold
        self.enable_duplicate_suppression = enable_duplicate_suppression
        self._last_suppressed_duplicates: List[Dict[str, Any]] = []

    @property
    def last_suppressed_duplicates(self) -> List[Dict[str, Any]]:
        """Return diagnostic records of any duplicate passages suppressed in the last retrieval."""
        return list(self._last_suppressed_duplicates)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        threshold: Optional[float] = None,
        doc_id: Optional[str] = None,
        alpha: Optional[float] = None,
        normalize_dense: bool = True,
        suppress_duplicates: Optional[bool] = None,
        duplicate_threshold: Optional[float] = None,
        fusion_method: str = "linear",
        lexical_metric: str = "overlap",
        workspace_id: Optional[str] = None,
    ) -> List[RetrievedPassage]:
        """Retrieve the most relevant document blocks for a user or system query.

        Args:
            query: Query text string.
            top_k: Maximum number of passages to return.
            threshold: Minimum hybrid similarity score threshold. Defaults to self.default_threshold.
            doc_id: Optional document identifier filter.
            alpha: Weight for dense semantic similarity vs lexical match (0.0 to 1.0).
            normalize_dense: When True, applies non-negative rectification (ReLU) to dense cosine scores.
            suppress_duplicates: Whether to filter out near-identical duplicate passages.
            duplicate_threshold: Similarity cutoff [0.0, 1.0] for duplicate suppression.
            fusion_method: 'linear' for weighted linear combination, or 'rrf' for Reciprocal Rank Fusion.
            lexical_metric: 'overlap' for token overlap cosine, or 'bm25' for Okapi BM25 scoring.
            workspace_id: Optional workspace ID filter for multi-tenant isolation.

        Returns:
            Ranked list of unique RetrievedPassage objects with full provenance.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        eff_alpha = self.default_alpha if alpha is None else float(alpha)
        eff_threshold = self.default_threshold if threshold is None else float(threshold)
        eff_suppress = self.enable_duplicate_suppression if suppress_duplicates is None else bool(suppress_duplicates)
        eff_dup_thresh = self.duplicate_threshold if duplicate_threshold is None else float(duplicate_threshold)

        # Load blocks and embedding matrix from store matching current embedding engine
        blocks_meta, matrix = self.store.get_all_embeddings(
            engine_name=self.embedding_engine.engine_name,
            workspace_id=workspace_id,
        )
        if not blocks_meta or len(matrix) == 0:
            return []

        # 1. Dense Semantic Scoring
        q_vec = self.embedding_engine.embed_texts([cleaned_query])  # Shape: (1, D)
        dense_scores = (q_vec @ matrix.T)[0]                        # Shape: (N,)

        # Filter indices by doc_id if specified
        valid_indices = [
            i for i, meta in enumerate(blocks_meta)
            if not doc_id or meta["doc_id"] == doc_id
        ]
        if not valid_indices:
            return []

        # 2. Lexical Scoring (Token Overlap or BM25)
        query_tokens = tokenize_text(cleaned_query)
        corpus_token_lists = [
            list(tokenize_text(blocks_meta[i]["text"])) for i in valid_indices
        ]

        if lexical_metric == "bm25":
            bm25_vals = compute_bm25_scores(list(query_tokens), corpus_token_lists)
            lexical_scores = {idx: bm25_vals[pos] for pos, idx in enumerate(valid_indices)}
        else:
            lexical_scores = {
                idx: compute_lexical_similarity(query_tokens, set(corpus_token_lists[pos]))
                for pos, idx in enumerate(valid_indices)
            }

        # 3. Score Fusion: Linear or Reciprocal Rank Fusion (RRF)
        scored_candidates: List[RetrievedPassage] = []

        if fusion_method == "rrf":
            # Rank indices by dense and lexical independently
            dense_ranked = sorted(valid_indices, key=lambda i: float(dense_scores[i]), reverse=True)
            lex_ranked = sorted(valid_indices, key=lambda i: lexical_scores[i], reverse=True)

            rrf_map = reciprocal_rank_fusion([dense_ranked, lex_ranked], weights=[eff_alpha, 1.0 - eff_alpha], k=60)
            max_rrf = max(rrf_map.values()) if rrf_map else 1.0

            for idx in valid_indices:
                meta = blocks_meta[idx]
                raw_dense = float(dense_scores[idx])
                norm_dense = rectify_dense_score(raw_dense) if normalize_dense else raw_dense
                lex_score = lexical_scores[idx]
                rrf_val = rrf_map.get(idx, 0.0)
                norm_rrf = (rrf_val / max_rrf) if max_rrf > 0 else 0.0

                if norm_rrf >= eff_threshold:
                    scored_candidates.append(
                        RetrievedPassage(
                            doc_id=meta["doc_id"],
                            document_name=meta.get("document_name", ""),
                            page_number=meta["page_number"],
                            block_id=meta["block_id"],
                            block_type=meta["block_type"],
                            text=meta["text"],
                            bounding_box=meta["bounding_box"],
                            confidence=meta["confidence"],
                            similarity_score=round(norm_rrf, 4),
                            retrieval_method="hybrid_rrf",
                            metadata={
                                "raw_dense_score": round(raw_dense, 4),
                                "normalized_dense_score": round(norm_dense, 4),
                                "lexical_score": round(lex_score, 4),
                                "rrf_score": round(rrf_val, 6),
                                "hybrid_score": round(norm_rrf, 4),
                                "fusion": "rrf",
                                "lexical_metric": lexical_metric,
                            },
                        )
                    )
        else:
            # Linear Fusion (Default)
            for idx in valid_indices:
                meta = blocks_meta[idx]
                raw_dense = float(dense_scores[idx])
                lex_score = lexical_scores[idx]

                hybrid_score, norm_dense = compute_hybrid_score(
                    dense_score=raw_dense,
                    lexical_score=lex_score,
                    alpha=eff_alpha,
                    normalize_dense=normalize_dense,
                )

                if hybrid_score >= eff_threshold:
                    if eff_alpha >= 1.0:
                        method_name = "dense"
                    elif eff_alpha <= 0.0:
                        method_name = "lexical" if lexical_metric == "overlap" else f"lexical_{lexical_metric}"
                    else:
                        method_name = "hybrid" if lexical_metric == "overlap" else f"hybrid_{lexical_metric}"

                    scored_candidates.append(
                        RetrievedPassage(
                            doc_id=meta["doc_id"],
                            document_name=meta.get("document_name", ""),
                            page_number=meta["page_number"],
                            block_id=meta["block_id"],
                            block_type=meta["block_type"],
                            text=meta["text"],
                            bounding_box=meta["bounding_box"],
                            confidence=meta["confidence"],
                            similarity_score=round(hybrid_score, 4),
                            retrieval_method=method_name,
                            metadata={
                                "raw_dense_score": round(raw_dense, 4),
                                "normalized_dense_score": round(norm_dense, 4),
                                "dense_score": round(norm_dense if normalize_dense else raw_dense, 4),
                                "lexical_score": round(lex_score, 4),
                                "hybrid_score": round(hybrid_score, 4),
                                "alpha": round(eff_alpha, 2),
                                "embedding_engine": meta.get("embedding_engine", ""),
                                "lexical_metric": lexical_metric,
                            },
                        )
                    )

        # Sort descending by similarity score
        scored_candidates.sort(key=lambda x: x.similarity_score, reverse=True)

        # 3. Duplicate Passage and Repeated Header Suppression
        self._last_suppressed_duplicates = []
        if not eff_suppress:
            return scored_candidates[:top_k]

        filtered_results: List[RetrievedPassage] = []
        for candidate in scored_candidates:
            is_dup = False
            for accepted in filtered_results:
                sim = compute_text_similarity(candidate.text, accepted.text)
                if sim >= eff_dup_thresh:
                    is_dup = True
                    self._last_suppressed_duplicates.append({
                        "suppressed_doc_id": candidate.doc_id,
                        "suppressed_page": candidate.page_number,
                        "suppressed_block_id": candidate.block_id,
                        "matched_doc_id": accepted.doc_id,
                        "matched_page": accepted.page_number,
                        "matched_block_id": accepted.block_id,
                        "similarity": round(sim, 4),
                        "text_snippet": candidate.text[:60],
                    })
                    break

            if not is_dup:
                filtered_results.append(candidate)

            if len(filtered_results) >= top_k:
                break

        return filtered_results
