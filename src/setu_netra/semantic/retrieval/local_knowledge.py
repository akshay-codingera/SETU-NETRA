"""
local_knowledge.py: Local knowledge retrieval interface for SETU-NETRA.

Why this file exists:
Provides an offline reference retrieval interface for grounding questions in curated
academic glossaries and textbook citations without requiring external APIs, vector DBs,
or internet access.
"""

from typing import List, Sequence, Tuple
from setu_netra.core.contracts import RetrievedKnowledgeItem
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine


# Curated academic reference collection
LOCAL_KNOWLEDGE_ENTRIES: List[Tuple[str, str, str, str]] = [
    (
        "ref_convolution_complexity",
        "2D Spatial Convolution Computational Complexity",
        (
            "For an image of spatial dimensions H x W and a 2D filter kernel of size K x K "
            "with unit stride and no padding, each of the ~H*W output pixels requires K*K multiplications "
            "and additions, yielding an asymptotic computational complexity of O(H * W * K^2)."
        ),
        "Digital Image Processing (Gonzalez & Woods, 4th Ed.)",
    ),
    (
        "ref_tcp_connection_oriented",
        "TCP Protocol Transport Characteristics",
        (
            "Transmission Control Protocol (TCP) is a connection-oriented, reliable transport protocol. "
            "It establishes a connection using a three-way handshake and guarantees in-order, error-checked "
            "packet delivery, in contrast to the connectionless User Datagram Protocol (UDP)."
        ),
        "Computer Networking: A Top-Down Approach (Kurose & Ross)",
    ),
    (
        "ref_asymptotic_complexity",
        "Asymptotic Running Time and Big-O Notation",
        (
            "Big-O notation formalizes the upper bound of an algorithm's runtime growth rate as the input "
            "size grows asymptotically large, enabling platform-independent complexity analysis."
        ),
        "Introduction to Algorithms (CLRS, 3rd Ed.)",
    ),
    (
        "ref_india_executive_governance",
        "Executive Structure of the Republic of India",
        (
            "Under the Constitution of India, the Prime Minister serves as the chief executive and head of "
            "government, leading the Union Council of Ministers, while the President is the constitutional "
            "head of state."
        ),
        "Constitution of India, Articles 74 and 75",
    ),
]


class LocalKnowledgeRetriever:
    """Offline reference retrieval engine grounded in local textbook definitions."""

    def __init__(self, embedding_engine: BaseEmbeddingEngine):
        self._engine = embedding_engine
        self._entries = LOCAL_KNOWLEDGE_ENTRIES
        self._entry_texts = [f"{title}. {passage}" for _, title, passage, _ in self._entries]
        self._entry_vectors = self._engine.embed_texts(self._entry_texts)

    def retrieve(
        self,
        query: str,
        threshold: float = 0.35,
        top_k: int = 1,
    ) -> List[RetrievedKnowledgeItem]:
        """Retrieve the most relevant curated reference passage for a query.

        Args:
            query: Query text string.
            threshold: Minimum cosine similarity threshold.
            top_k: Maximum number of passages to return.

        Returns:
            List of RetrievedKnowledgeItem objects.
        """
        cleaned = query.strip()
        if not cleaned or len(self._entry_vectors) == 0:
            return []

        q_vec = self._engine.embed_texts([cleaned])
        similarities = (q_vec @ self._entry_vectors.T)[0]

        results: List[RetrievedKnowledgeItem] = []
        ranked_indices = similarities.argsort()[::-1]

        for idx in ranked_indices[:top_k]:
            score = float(similarities[idx])
            if score >= threshold:
                source_id, title, passage, citation = self._entries[idx]
                results.append(
                    RetrievedKnowledgeItem(
                        source_id=source_id,
                        title=f"{title} ({citation})",
                        passage=passage,
                        similarity_score=round(score, 4),
                    )
                )

        return results
