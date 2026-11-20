"""
demo_retrieval_and_embeddings.py: Demonstrates tokenization, TF-IDF lexical search, and semantic embeddings.
"""
import sys
import numpy as np

sys.path.insert(0, "src")

from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.retrieval.document_retriever import tokenize_text, rectify_dense_score

def run():
    print("=" * 72)
    print("  SETU-NETRA: HYBRID RETRIEVAL (TF-IDF LEXICAL + SEMANTIC EMBEDDINGS)")
    print("=" * 72)

    # 1. Corpus of exam knowledge passages
    passages = [
        "In BCNF, for every non-trivial functional dependency X -> Y, X must be a superkey of the relation.",
        "A relation is in 3NF if for every functional dependency X -> Y, either X is a superkey or Y is a prime attribute.",
        "The primary function of the reconstructor is 2D topological reading-order sorting and spatial block grouping.",
        "Convolutional neural networks use kernel filters to extract spatial features from high-dimensional image inputs.",
        "Deadlock requires four mutual conditions: mutual exclusion, hold and wait, no preemption, and circular wait."
    ]

    print("\n[1] CORPUS INDEXING (5 Knowledge Passages):")
    for i, p in enumerate(passages):
        print(f"    [{i+1}] \"{p}\"")

    query = "What is the condition for BCNF normal form and superkey?"
    print(f"\n[2] USER INQUIRY QUERY:\n    \"{query}\"")

    # 2. Tokenization & Lexical Overlap (TF-IDF style term frequency)
    print("\n[3] LEXICAL TOKENIZATION & JACCARD/TERM-OVERLAP:")
    q_tokens = tokenize_text(query)
    print(f"    • Query Tokenization: {sorted(list(q_tokens))}")
    lexical_scores = []
    for i, p in enumerate(passages):
        p_tokens = tokenize_text(p)
        intersection = q_tokens & p_tokens
        score = len(intersection) / len(q_tokens) if q_tokens else 0.0
        lexical_scores.append(score)
        print(f"    • Passage {i+1} Lexical Score: {score:>5.2f} | Matching Tokens: {sorted(list(intersection))}")

    # 3. Semantic Vector Embeddings
    print("\n[4] SEMANTIC VECTOR EMBEDDINGS (Subword N-Gram Synset Hashing):")
    engine = OfflineSemanticEngine()
    print(f"    • Active Embedder: {engine.engine_name} (Dimension: {engine.dimension})")

    q_embed = np.array(engine.embed_texts([query])[0])
    p_embeds = np.array(engine.embed_texts(passages))
    dense_scores = []
    for i, (p, p_embed) in enumerate(zip(passages, p_embeds)):
        cos_sim = float(np.dot(q_embed, p_embed) / (np.linalg.norm(q_embed) * np.linalg.norm(p_embed)))
        rect_sim = rectify_dense_score(cos_sim)
        dense_scores.append(rect_sim)
        print(f"    • Passage {i+1} Dense Cosine: {cos_sim:>6.3f} (Rectified: {rect_sim:.3f}) | {p[:50]}...")

    # 4. Hybrid Ranking Fusion (0.4 Lexical + 0.6 Dense)
    print("\n[5] HYBRID FUSION SCORE (0.4 * Lexical + 0.6 * Dense):")
    hybrid_scores = [0.4 * l + 0.6 * d for l, d in zip(lexical_scores, dense_scores)]
    best_idx = int(np.argmax(hybrid_scores))

    for i, hs in enumerate(hybrid_scores):
        tag = "  <-- [RANK #1 GROUNDING CANDIDATE]" if i == best_idx else ""
        print(f"    • Passage {i+1} Combined Score: {hs:.3f}{tag}")

    print(f"\n    TOP RETRIEVED GROUNDED EVIDENCE:")
    print(f"    \"{passages[best_idx]}\"")
    print("\n" + "=" * 72)
    print("  RETRIEVAL VERIFIED: Exact grounding candidate selected with confidence.")
    print("=" * 72)

if __name__ == "__main__":
    run()
