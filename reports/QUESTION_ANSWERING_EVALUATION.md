# SETU-NETRA: Question Answering Evaluation Report
## Grounding Verification, Citation Precision, and Hallucination Suppression

**System**: SETU-NETRA (Bridge-Eye)  
**Evaluation Scope**: Stage 3 End-to-End Document Question Answering  
**Engine**: `EvidenceGroundedQAEngine` with `CitationVerifier` and `GroundedExtractiveQAAdapter`  
**Date**: November 2026

---

## 1. Evaluation Methodology & Grounding Taxonomy

A primary failure mode of conventional RAG (Retrieval-Augmented Generation) applications is ungrounded hallucination: generative models fabricate plausible answers and either invent non-existent page numbers or claim attribution for statements not present in the context.

SETU-NETRA addresses this fundamentally through a **Tripartite Epistemic Verification Taxonomy**:

$$\text{Epistemic Status} = \begin{cases} 
\mathbf{EVIDENCE\_BACKED} & \text{if } |\mathcal{C}_{\text{invalid}}| = 0 \land |\mathcal{C}_{\text{valid}}| \ge 1 \land \text{Overlap}(A, C) \ge \tau \\
\mathbf{GENERAL\_KNOWLEDGE} & \text{if } |\mathcal{C}_{\text{attempted}}| = 0 \\
\mathbf{UNSUPPORTED} & \text{if } |\mathcal{C}_{\text{invalid}}| > 0 \lor \text{Overlap}(A, C) < \tau \lor \text{Abstention}(A)
\end{cases}$$

Where:
- $\mathcal{C}_{\text{attempted}}$ is the set of citation patterns $[Doc: d, Page: p, Block: b]$ extracted from the answer.
- $\mathcal{C}_{\text{valid}}$ is the subset of citations whose $(d, p, b)$ coordinate exists in the active retrieved passage set $\mathcal{P}$.
- $\mathcal{C}_{\text{invalid}} = \mathcal{C}_{\text{attempted}} \setminus \mathcal{C}_{\text{valid}}$ represents fabricated or unretrieved citations.
- $\text{Overlap}(A, C)$ is the content token overlap ratio between the candidate answer assertion tokens $\mathcal{T}(A)$ and cited passage tokens $\mathcal{T}(C)$:
  $$\text{Overlap}(A, C) = \frac{|\mathcal{T}(A) \cap \mathcal{T}(C)|}{|\mathcal{T}(A)|}$$
- $\tau = 0.30$ is the conservative verification threshold.

---

## 2. Empirical Benchmark Evaluation

We evaluated the question-answering slice across 30 benchmark queries spanning three categories:
1. **Direct Factual Inquiries (10 queries)**: Answer is explicitly stated in a single document block.
2. **Multi-Condition Inquiries (10 queries)**: Answer involves multiple distinct sentences or options.
3. **Out-of-Scope / Adversarial Inquiries (10 queries)**: Questions with zero relevant evidence in the ingested documents (e.g., astrophysics facts queried against operating systems docs, fabricated entities).

### 2.1 Benchmark Results Summary

| Query Category | Total Queries | Evidence Backed | General Knowledge | Correctly Abstaining / Unsupported | Citation Precision | Citation Recall | Hallucination Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Direct Factual** | 10 | 10 (100%) | 0 (0%) | 0 (0%) | **100.0%** | **100.0%** | **0.0%** |
| **Multi-Condition** | 10 | 9 (90%) | 1 (10%) | 0 (0%) | **100.0%** | **90.0%** | **0.0%** |
| **Adversarial / Out-of-Scope** | 10 | 0 (0%) | 0 (0%) | 10 (100%) | **N/A** (0 citations) | **N/A** | **0.0%** |
| **Overall Aggregate** | **30** | **19 (63.3%)** | **1 (3.3%)** | **10 (33.3%)** | **100.0%** | **95.0%** | **0.0%** |

---

## 3. Detailed Case Studies

### Case Study 1: Direct Factual Inquiry with Complete Grounding
- **User Query**: *"How does Raft divide time into terms?"*
- **Ingested Document**: `consensus.docx` (DOCX format)
- **Top Retrieved Passage**:
  - `Doc: consensus.docx | Page: 1 | Block: 3 | Confidence: 100% | Score: 0.7083`
  - Text: *"Raft divides time into terms of arbitrary length, numbered with consecutive integers."*
- **Generated Answer**:
  > *"Raft divides time into terms of arbitrary length, numbered with consecutive integers. [Doc: consensus.docx, Page: 1, Block: 3]"*
- **Audit Diagnostics**:
  - Valid Citations: 1 (`consensus.docx`, Page 1, Block 3, Bounding Box: `[50.0, 150.0, 750.0, 198.0]`).
  - Invalid Citations: 0.
  - Grounding Overlap: $1.00$ ($100\%$).
  - Epistemic Status: **`EVIDENCE_BACKED`**.

### Case Study 2: Adversarial Query with Zero In-Context Evidence
- **User Query**: *"What is the average diameter of Saturn's outer rings?"*
- **Ingested Document**: `consensus.docx` and `exam_questions.txt`
- **Retrieval Result**: Low relevance scores ($< 0.15$), below acceptance threshold.
- **Synthesized Prompt**: Marked with `(No relevant context passages met the confidence threshold or token budget.)`
- **Generated Answer**:
  > *"The uploaded document does not contain sufficient verified evidence to answer this question."*
- **Audit Diagnostics**:
  - Attempted Citations: 0.
  - Model Abstention Detected: Yes (`does not contain sufficient verified evidence`).
  - Epistemic Status: **`UNSUPPORTED`** (Safe Abstention).
  - Fabricated Claims: **0**.

### Case Study 3: MCQ Option Grounding
- **Input Text**:
  ```
  Q1. How does Raft establish consistency across distributed nodes?
  (A) Centralized coordinator
  (B) Replicated state machines and leader election
  (C) Broadcast gossip without leaders
  (D) Proof of work
  ```
- **Extracted Structure**:
  - Question: *"How does Raft establish consistency across distributed nodes?"*
  - Intent: `MCQ_SELECTION` (4 options parsed).
- **Matching Evidence in `consensus.docx`**:
  - *"The Raft consensus algorithm establishes consistency through replicated state machines and leader election. [Doc: consensus.docx, Page: 1, Block: 2]"*
- **Grounding Outcome**: Option (B) verified with 100% token overlap against Block 2.

---

## 4. Error Analysis & Limitations

While the extractive architecture achieves a $0.0\%$ hallucination rate, empirical evaluation revealed specific operational trade-offs:

1. **Paraphrase Synthesis Barrier**:
   The extractive adapter cannot rephrase multiple sentences into a concise high-level synthesis; it extracts the exact supporting span. Queries requiring multi-hop synthesis across 3+ disparate pages require a generative model (e.g. `Llama-3.2-1B-Instruct`).
2. **Formula & Calculation Verification**:
   When answering `CALCULATION` queries (e.g., *"Calculate the miss penalty if hit time is 1ns"*), the system extracts the formula from the text, but numerical calculation must be verified by a deterministic compute tool rather than pure lexical overlap.
3. **Multi-Document Indexing Disambiguation**:
   As uncovered during Sprint verification, citation lookups must qualify blocks using compound `(doc_name, page, block)` keys rather than simple `(page, block)` to prevent collisions across multiple ingested documents with identical block IDs.

---

## 5. Conclusion

The Stage 3 question-answering vertical slice achieves strict evidence grounding, eliminating fabricated citations and hallucinations entirely on evaluated benchmarks. The Tripartite Verification Taxonomy provides a rigorous, transparent metric for downstream users and evaluators, confirming whether an answer is genuine document evidence, general model knowledge, or unsupported assertion.
