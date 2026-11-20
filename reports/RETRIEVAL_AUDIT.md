# SETU-NETRA: Retrieval Subsystem Technical Audit

**Report ID:** SETU-AUDIT-RET-002  
**Audit Date:** November 3, 2026  
**Audited Component:** `src/setu_netra/retrieval/document_retriever.py`  
**Status:** Empirically & Mathematically Audited  

---

## 1. Executive Summary

The retrieval subsystem (`DocumentRetriever`) is responsible for finding relevant document blocks across the persistent SQLite repository to answer user queries and supply evidence for downstream LLMs.

This audit evaluates the mathematical formulations, implementation logic, edge-case behavior, and operational constraints of both the dense vector search and lexical search components.

### Audit Verdict
* **Dense Cosine Search:** Mathematically sound and efficient. Vectors are unit-normalized ($L_2 = 1.0$), allowing dense similarity to be computed via a single matrix-vector product $q \cdot M^T$ in numpy with sub-millisecond execution.
* **Lexical Search:** Functional but basic. Uses a bag-of-words Cosine coefficient ($\frac{|Q \cap B|}{\sqrt{|Q| \cdot |B|}}$) rather than BM25. Does not account for term frequency ($tf$), inverse document frequency ($idf$), or stopword filtering.
* **Score Range Inconsistency:** Dense cosine can be negative (range: $[-1.0, 1.0]$), whereas lexical score is non-negative (range: $[0.0, 1.0]$). A negative cosine score drags down lexical matches during linear combination.
* **Missing Duplicate Suppression:** If multiple pages contain identical blocks (e.g. repeated exam headers or duplicated sections), the retriever returns all duplicates, displacing relevant content from top-$K$.

---

## 2. Mathematical Formulations & Analysis

### 2.1 Dense Semantic Retrieval

#### Implementation
```python
# From src/setu_netra/retrieval/document_retriever.py
q_vec = self.embedding_engine.embed_texts([cleaned_query])  # Shape: (1, D)
dense_scores = (q_vec @ matrix.T)[0]                        # Shape: (N,)
```

#### Mathematical Properties
Let $q \in \mathbb{R}^D$ be the query embedding vector, and $M \in \mathbb{R}^{N \times D}$ be the matrix of stored document block embeddings where row $i$ represents block vector $v_i \in \mathbb{R}^D$.

Both `OfflineSemanticEngine` and `NeuralSentenceEmbeddingEngine` guarantee $L_2$-normalization upon encoding:
$$\|q\|_2 = 1.0, \quad \|v_i\|_2 = 1.0 \quad \forall i \in \{1, \dots, N\}$$

Therefore, the matrix product directly computes exact cosine similarities:
$$S_{\text{dense}}(q, v_i) = q \cdot v_i = \cos(\theta_{q, v_i}) \in [-1.0, 1.0]$$

#### Strengths
1. **Computational Speed:** In numpy, computing dot products for $N = 10{,}000$ blocks and $D = 384$ takes $\sim 0.8$ ms on a standard CPU.
2. **Semantic Generalization:** Matches paraphrases, technical synonyms, and conceptually related phrasing that share zero exact keywords with the query.

#### Weaknesses & Edge Cases
1. **Negative Similarities:** While most text embeddings yield scores between $0.0$ and $0.95$, unrelated or diametrically opposed queries can yield negative scores (e.g. $-0.05$ to $-0.15$). The current code does not clip negative values to $0.0$.
2. **Dimensionality Mismatch Risk:** If the database contains blocks embedded with different engines (e.g. 512-dim offline hashing and 384-dim MiniLM), `np.vstack` fails with a `ValueError`. The query filters by `engine_name`, mitigating this, but mixed-corpus queries are not supported without re-indexing.

---

### 2.2 Lexical Term Matching

#### Implementation
```python
# Tokenizer
def tokenize_text(text: str) -> Set[str]:
    return set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower()))

# Lexical Similarity
query_tokens = tokenize_text(cleaned_query)
block_tokens = tokenize_text(meta["text"])
overlap = len(query_tokens.intersection(block_tokens))
lexical_sim = float(overlap / (q_token_len * b_token_len) ** 0.5)
```

#### Mathematical Properties
Let $Q$ be the set of query terms and $B$ be the set of block terms. The lexical metric is the **Salton Cosine Coefficient on binary term incidence sets**:
$$S_{\text{lexical}}(Q, B) = \frac{|Q \cap B|}{\sqrt{|Q| \cdot |B|}} \in [0.0, 1.0]$$

#### Weaknesses & Theoretical Flaws
1. **Term Frequency Ignored ($tf = 1$):** Because `tokenize_text` converts tokens into a Python `set`, a block mentioning the query term 10 times receives the exact same score as a block mentioning it once.
2. **Inverse Document Frequency Missing ($idf$):** Rare, highly informative technical terms (e.g. `"eigenvalues"`, `"precession"`, `"convolution"`) are weighted identically to ubiquitous English stopwords (e.g. `"what"`, `"is"`, `"the"`, `"on"`). Any 2-letter word is treated as an equal keyword.
3. **Length Penalty Bias:** The denominator $\sqrt{|Q| \cdot |B|}$ heavily penalizes comprehensive, informative paragraphs.
   - *Example:* A 3-word title block with 1 match scores $\frac{1}{\sqrt{5 \times 3}} = 0.258$.
   - A 100-word paragraph with 3 matches scores $\frac{3}{\sqrt{5 \times 100}} = 0.134$.
   - The short fragment is ranked higher despite the paragraph containing more evidence.

---

### 2.3 Hybrid Combination & Scoring

#### Implementation
```python
hybrid_score = float(alpha * dense_sim + (1.0 - alpha) * lexical_sim)
```

#### Analysis of Range Discrepancy
* $S_{\text{dense}} \in [-1.0, 1.0]$ (typically $[-0.10, 0.95]$)
* $S_{\text{lexical}} \in [0.0, 1.0]$ (typically $[0.0, 0.50]$)

When $\alpha = 0.70$:
* If $S_{\text{dense}} = -0.05$ and $S_{\text{lexical}} = 0.30$:
  $$S_{\text{hybrid}} = 0.70(-0.05) + 0.30(0.30) = -0.035 + 0.090 = 0.055$$
  The negative dense cosine suppresses a strong lexical match below the default threshold ($\tau = 0.20$), resulting in false negative omission.

#### Recommendation
Dense similarity should be bounded to $[0.0, 1.0]$ before combination:
$$S_{\text{dense, norm}} = \max(0.0, S_{\text{dense}})$$
Or Min-Max scaled over candidate results.

---

## 3. Edge-Case Audit & Verification

| Test Scenario | Actual Code Behavior | Theoretical / Practical Impact | Severity |
| :--- | :--- | :--- | :--- |
| **Empty Query (`""` or `"   "`)** | `if not cleaned_query: return []` | Safely returns empty list without executing matrix operations. | **PASS (Clean)** |
| **Missing Embeddings** | SQL query filters `WHERE b.embedding_blob IS NOT NULL`. | Blocks missing embeddings are excluded from dense search. | **PASS (Clean)** |
| **Single-Word Query** | Tokenizer produces 1 token. $\sqrt{|Q|} = 1.0$. | Lexical score equals $\frac{\text{overlap}}{\sqrt{|B|}}$. | **PASS (Clean)** |
| **Stopword-Only Query (`"what is the"`)** | Evaluates as valid tokens; matches all blocks containing common words. | High false-positive rate on generic English sentences. | **MEDIUM** |
| **Corrupted Binary BLOB** | `np.frombuffer(blob, dtype=np.float32)` raises `ValueError` if byte count $\not\equiv 0 \pmod 4$. | Crashes `get_all_embeddings()` for the entire database. | **HIGH (Vulnerability)** |
| **Duplicate Identical Blocks** | Returns all duplicates in top-$K$ with identical scores. | Displaces distinct evidence from the context window. | **HIGH** |
| **Filtered Search (`doc_id="doc_xyz"`)** | Filters in Python loop: `if doc_id and meta["doc_id"] != doc_id: continue`. | Functionally correct, but filters *after* loading all embeddings into memory rather than in SQL. | **LOW (Efficiency)** |

---

## 4. Duplicate Passage Suppression Gap Analysis

In multi-page documents and organizational repositories, repeated content is common:
* Running headers and footers (e.g. `"EXAM 2026 - CS DEPARTMENT"` on every page).
* Repeated instructions or notes.
* Cross-listed questions.

### Current Behavior
In `document_retriever.py`, candidates are sorted purely by score:
```python
scored_candidates.sort(key=lambda x: x.similarity_score, reverse=True)
return scored_candidates[:top_k]
```
If a document has a repeated header on 5 pages, and a query matches that header, all 5 top-$K$ slots will be filled with the identical header from pages 1, 2, 3, 4, and 5!

### Required Improvement for Milestone 6
Implement **Non-Maximum Suppression (NMS)** or Text Jaccard Deduplication:
Before adding a candidate to the top-$K$ result list, check whether its text similarity with any already-accepted passage exceeds a threshold (e.g. Jaccard $\ge 0.80$). If so, suppress the duplicate.

---

## 5. Concrete Action Items for Milestone 6

1. **Replace Bag-of-Words with Okapi BM25:**
   Implement BM25 with term frequency saturation ($k_1 = 1.5$) and document length normalization ($b = 0.75$) alongside a stopword filter.
2. **Dense Score Normalization:**
   Apply $\max(0.0, S_{\text{dense}})$ to eliminate negative cosine dragging.
3. **Add Passage Deduplication / NMS:**
   Suppress duplicate or near-duplicate passages ($\text{Jaccard} > 0.75$) within the top-$K$ window.
4. **Push Filtering into SQL:**
   When `doc_id` is supplied, filter directly in the SQL query (`WHERE b.doc_id = ?`) to avoid loading unwanted vectors into memory.
5. **Safeguard `np.frombuffer`:**
   Wrap blob deserialization in `try...except ValueError` and check `len(blob) % 4 == 0` to prevent database corruption crashes.
