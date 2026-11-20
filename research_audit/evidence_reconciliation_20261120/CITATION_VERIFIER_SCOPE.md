# SETU-NETRA Citation Verifier Scope and Limitations Audit Report

**Audit Phase:** Post-Master Evidence Reconciliation  
**Date:** 2026-11-20  
**Investigator:** Senior Natural Language Processing & Epistemic Verification Auditor  
**Scope:** Citation Verification Implementation (`src/setu_netra/qa/verifier.py`), Lexical Overlap vs Semantic Entailment, and Evaluation Scope Limitations  
**Primary Reference Files:**
- [`src/setu_netra/qa/verifier.py`](file:///d:/Projects/Setu-Netra/src/setu_netra/qa/verifier.py)
- [`QA_QUERY_LEVEL_RECONCILIATION.csv`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/QA_QUERY_LEVEL_RECONCILIATION.csv)
- [`QA_METRIC_RECALCULATION.json`](file:///d:/Projects/Setu-Netra/research_audit/evidence_reconciliation_20261120/QA_METRIC_RECALCULATION.json)
- [`benchmarks/results/aggregated/qa_quality_evaluation_summary.json`](file:///d:/Projects/Setu-Netra/benchmarks/results/aggregated/qa_quality_evaluation_summary.json)

---

## 1. Technical Implementation Analysis of `CitationVerifier`

The Master Audit Report and early manuscript drafts described `CitationVerifier` as an epistemic grounding auditor that enforces semantic citation correctness.
Reviewers requested a forensic audit of the source code to determine whether the mechanism is **lexical, structural, or semantic**.

### Forensic Inspection of `src/setu_netra/qa/verifier.py`
Direct analysis of the verifier implementation reveals that it is built on three deterministic components:

1. **Structural Coordinate Parsing (Regex):**
   ```python
   CITATION_REGEX = re.compile(
       r"\[Doc:\s*(?P<doc>[^,\]]+),\s*Page:\s*(?P<page>\d+),\s*Block:\s*(?P<block>\d+)\]",
       re.IGNORECASE,
   )
   ```
   Extracts document filename, physical page number, and layout block index. It performs a set lookup against the database of retrieved chunks to verify that the cited block actually exists in the ingested corpus.
2. **Lexical Token Overlap (`compute_entailment_score`):**
   ```python
   def compute_entailment_score(answer_text: str, cited_passages: Sequence[RetrievedPassage]) -> float:
       clean_ans = CITATION_REGEX.sub("", answer_text).strip()
       ans_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", clean_ans.lower())) - STOPWORDS
       ev_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", evidence_text))
       overlap = len(ans_tokens.intersection(ev_tokens))
       return round(float(overlap / len(ans_tokens)), 4)
   ```
   Calculates unweighted token set intersection between the answer tokens and the cited document tokens.
3. **Rule-Based Negation & Antonym Scans (`detect_contradictory_evidence`):**
   Scans for hardcoded polar opposites: `("increase", "decrease")`, `("safe", "unsafe")`, `("allowed", "prohibited")`, `("valid", "invalid")`.

### Architectural Conclusion
`CitationVerifier` is a **structural and lexical heuristic verifier**. It does **NOT** run a neural Natural Language Inference (NLI) cross-encoder, does not construct formal logic proofs, and does not evaluate semantic entailment beyond token overlap.

---

## 2. Distinction: Lexical Overlap vs Semantic Entailment

To maintain scientific integrity in an IEEE submission, the following boundaries must be explicitly honored:
1. **Lexical Overlap $\ne$ Semantic Truth:** An answer can achieve high lexical token overlap with a passage while altering the factual relationship (e.g. *"Alice defeated Bob"* vs *"Bob defeated Alice"* share 100% token overlap but assert opposing truths).
2. **The Role of ER-SP:** True semantic contradiction detection in SETU-NETRA is handled upstream by **ER-SP** (`models/evidence/er_sp.pt`, 560k parameters), which evaluates dense interaction features between question and evidence chunks. `CitationVerifier` serves as a downstream lightweight post-processor to confirm bounding box coordinates and flag obvious negation inversions.

---

## 3. Critical Sample Size Limitation ($N=8$)

The QA quality benchmark in `qa_quality_evaluation_summary.json` reports:
- `unsupported_abstention_accuracy`: **$100.0\%$**
- `hallucination_rate_percent`: **$0.0\%$**

### Audit Caveat
These metrics were computed on **exactly eight evaluated questions**:
- 5 supported queries on distributed consensus (`consensus.docx`, `exam_questions.txt`).
- 3 unanswerable queries on quantum computing, number theory, and Irish corporate tax.

While the system correctly abstained on all 3 unanswerable queries, an evaluation of **8 samples has zero statistical power** to claim general immunity to hallucination.
In the manuscript, this must be stated transparently as:
*"In an initial proof-of-concept evaluation across 8 domain inquiries (5 supported, 3 out-of-domain unanswerable), SETU-NETRA successfully abstained on all 3 unanswerable questions without generating ungrounded claims. A larger-scale evaluation across diverse multi-document benchmarks remains future work."*
