"""
verifier.py: Citation grounding auditor and hallucination detection for SETU-NETRA.

Why this file exists:
Generative models frequently hallucinate facts or cite non-existent sources.
This module audits every answer assertion against actual retrieved document blocks,
extracts citations in the format [Doc: <d>, Page: <p>, Block: <b>], verifies that the
cited blocks exist in the database, and categorizes the answer into the Tripartite
Verification Taxonomy: EVIDENCE_BACKED, GENERAL_KNOWLEDGE, or UNSUPPORTED.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from setu_netra.core.contracts import RetrievedPassage

CITATION_REGEX = re.compile(
    r"\[Doc:\s*(?P<doc>[^,\]]+),\s*Page:\s*(?P<page>\d+),\s*Block:\s*(?P<block>\d+)\]",
    re.IGNORECASE,
)


@dataclass
class CitationVerificationResult:
    """Detailed audit of citations and evidence grounding in a generated answer."""
    epistemic_status: str              # 'EVIDENCE_BACKED', 'GENERAL_KNOWLEDGE', 'UNSUPPORTED'
    grounding_score: float             # Overlap ratio in [0.0, 1.0]
    total_citations_found: int
    valid_citations: List[Dict[str, Any]]
    invalid_citations: List[Dict[str, Any]]
    cited_passages: List[RetrievedPassage]
    is_verified: bool
    audit_notes: List[str] = field(default_factory=list)
    has_contradictory_evidence: bool = False
    negation_mismatch: bool = False
    entailment_score: float = 1.0


NEGATION_TOKENS = {
    "not", "never", "no", "cannot", "cant", "can't", "wont", "won't",
    "isnt", "isn't", "arent", "aren't", "wasnt", "wasn't", "werent", "weren't",
    "doesnt", "doesn't", "dont", "don't", "didnt", "didn't", "neither", "nor",
    "without", "fails", "failed", "disallow", "disallowed", "prohibited", "prevented"
}

POLARITY_OPPOSITES = [
    ("increase", "decrease"),
    ("increases", "decreases"),
    ("safe", "unsafe"),
    ("allowed", "prohibited"),
    ("enable", "disable"),
    ("valid", "invalid"),
    ("prevents", "causes"),
]


def detect_negation_mismatch(answer_text: str, cited_passages: Sequence[RetrievedPassage]) -> Tuple[bool, Optional[str]]:
    """Detect polarity inversion or negation mismatch between answer assertions and cited sources."""
    ans_words = set(re.findall(r"\b\w+\b", answer_text.lower()))
    ans_neg = ans_words.intersection(NEGATION_TOKENS)

    cited_text = " ".join(p.text.lower() for p in cited_passages)
    cited_words = set(re.findall(r"\b\w+\b", cited_text))
    cited_neg = cited_words.intersection(NEGATION_TOKENS)

    if ans_neg and not cited_neg:
        return True, f"Negation divergence: Answer asserts negative polarity ({list(ans_neg)}) while cited evidence contains strictly affirmative text."
    return False, None


def detect_contradictory_evidence(passages: Sequence[RetrievedPassage]) -> Tuple[bool, List[str]]:
    """Detect conflicting or contradictory assertions across retrieved evidence passages."""
    contradictions: List[str] = []
    if len(passages) < 2:
        return False, contradictions

    stopwords = {"the", "a", "an", "and", "or", "to", "in", "of", "on", "at", "by", "for", "with", "is", "was", "were", "are", "it", "its"}

    for i in range(len(passages)):
        for j in range(i + 1, len(passages)):
            p1 = passages[i]
            p2 = passages[j]
            t1_words = set(re.findall(r"\b\w+\b", p1.text.lower()))
            t2_words = set(re.findall(r"\b\w+\b", p2.text.lower()))

            # Check overlap on content terms
            content_overlap = (t1_words & t2_words) - stopwords
            if len(content_overlap) >= 2:
                # Check for direct antonym pair
                for pos_word, neg_word in POLARITY_OPPOSITES:
                    if (pos_word in t1_words and neg_word in t2_words) or (neg_word in t1_words and pos_word in t2_words):
                        contradictions.append(
                            f"Contradictory evidence detected between p{p1.page_number} b{p1.block_id} ('{pos_word}') and p{p2.page_number} b{p2.block_id} ('{neg_word}')."
                        )
                        break

    return len(contradictions) > 0, contradictions


def compute_entailment_score(answer_text: str, cited_passages: Sequence[RetrievedPassage]) -> float:
    """Compute directional entailment coverage ratio of answer terms supported by cited evidence."""
    clean_ans = CITATION_REGEX.sub("", answer_text).strip()
    ans_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", clean_ans.lower()))
    ans_tokens -= {"the", "and", "this", "that", "with", "from", "for", "are", "was", "were", "been"}
    if not ans_tokens:
        return 1.0

    evidence_text = " ".join(p.text.lower() for p in cited_passages)
    ev_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", evidence_text))

    overlap = len(ans_tokens.intersection(ev_tokens))
    return round(float(overlap / len(ans_tokens)), 4)


class CitationVerifier:
    """Audits generated answers against verified retrieved context passages."""

    def __init__(self, min_overlap_threshold: float = 0.35):
        self.min_overlap_threshold = min_overlap_threshold

    def verify_answer(
        self,
        answer_text: str,
        retrieved_passages: Sequence[RetrievedPassage],
    ) -> CitationVerificationResult:
        """Audit an answer text against retrieved document passages.

        Args:
            answer_text: The candidate answer string containing potential citation tags.
            retrieved_passages: The exact passages retrieved for this query.

        Returns:
            CitationVerificationResult with verified status and matched passages.
        """
        audit_notes: List[str] = []

        # Check for explicit abstention
        lower_ans = answer_text.lower()
        if "does not contain sufficient" in lower_ans or "cannot be verified" in lower_ans or "insufficient evidence" in lower_ans:
            return CitationVerificationResult(
                epistemic_status="UNSUPPORTED",
                grounding_score=0.0,
                total_citations_found=0,
                valid_citations=[],
                invalid_citations=[],
                cited_passages=[],
                is_verified=True,
                audit_notes=["Model correctly abstained due to insufficient evidence."],
            )

        # Check for general knowledge disclaimer
        if "general knowledge" in lower_ans or "external knowledge" in lower_ans:
            return CitationVerificationResult(
                epistemic_status="GENERAL_KNOWLEDGE",
                grounding_score=0.0,
                total_citations_found=0,
                valid_citations=[],
                invalid_citations=[],
                cited_passages=[],
                is_verified=False,
                audit_notes=["Answer flagged as ungrounded external model knowledge."],
            )

        # Build index of available passages by document, page, and block_id
        passage_index: Dict[Any, RetrievedPassage] = {}
        for p in retrieved_passages:
            if p.doc_id:
                passage_index[(p.doc_id.lower().strip(), p.page_number, p.block_id)] = p
            if p.document_name:
                passage_index[(p.document_name.lower().strip(), p.page_number, p.block_id)] = p
            # Single-document fallback
            if (p.page_number, p.block_id) not in passage_index:
                passage_index[(p.page_number, p.block_id)] = p

        # Parse all citations in the answer
        citations_matches = list(CITATION_REGEX.finditer(answer_text))
        valid_citations: List[Dict[str, Any]] = []
        invalid_citations: List[Dict[str, Any]] = []
        matched_passages: List[RetrievedPassage] = []

        for m in citations_matches:
            doc = m.group("doc").strip()
            page = int(m.group("page").strip())
            block = int(m.group("block").strip())

            # Look up in retrieved passages (document-qualified first, then fallback)
            doc_key = doc.lower().strip()
            matched = (
                passage_index.get((doc_key, page, block))
                or passage_index.get((page, block))
            )
            if matched:
                valid_citations.append({
                    "document": doc,
                    "page": page,
                    "block_id": block,
                    "bounding_box": matched.bounding_box,
                    "confidence": matched.confidence,
                })
                if matched not in matched_passages:
                    matched_passages.append(matched)
            else:
                invalid_citations.append({
                    "document": doc,
                    "page": page,
                    "block_id": block,
                    "reason": "Cited page/block not found in retrieved context passages",
                })
                audit_notes.append(f"Invalid citation: Page {page}, Block {block} was not retrieved.")

        # Check whether any citations were attempted
        if not citations_matches:
            return CitationVerificationResult(
                epistemic_status="GENERAL_KNOWLEDGE",
                grounding_score=0.0,
                total_citations_found=0,
                valid_citations=[],
                invalid_citations=[],
                cited_passages=[],
                is_verified=False,
                audit_notes=["Answer contains no document citations; classified as external/general knowledge."],
            )

        # Compute grounding score based on content overlap with cited passages
        if not valid_citations:
            return CitationVerificationResult(
                epistemic_status="UNSUPPORTED",
                grounding_score=0.0,
                total_citations_found=len(citations_matches),
                valid_citations=[],
                invalid_citations=invalid_citations,
                cited_passages=[],
                is_verified=False,
                audit_notes=["No valid citations found supporting the answer assertions."],
            )

        # Calculate token overlap between answer text and cited passages
        answer_clean = CITATION_REGEX.sub("", answer_text)
        ans_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", answer_clean.lower()))
        ans_tokens -= {"the", "and", "this", "that", "with", "from", "for", "are", "was", "were", "been"}

        cited_tokens: Set[str] = set()
        for p in matched_passages:
            cited_tokens.update(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", p.text.lower()))

        if ans_tokens:
            overlap = len(ans_tokens & cited_tokens)
            grounding_score = overlap / len(ans_tokens)
        else:
            grounding_score = 1.0

        is_verified = (len(invalid_citations) == 0) and (grounding_score >= self.min_overlap_threshold)

        if is_verified:
            status = "EVIDENCE_BACKED"
            audit_notes.append(f"Answer successfully verified with {len(valid_citations)} valid citations (Grounding score: {grounding_score:.2f}).")
        else:
            status = "UNSUPPORTED"
            audit_notes.append(f"Answer failed verification: Grounding score {grounding_score:.2f} below threshold {self.min_overlap_threshold}.")

        # Check for negation mismatch & contradictory evidence across retrieved passages
        neg_mismatch, neg_note = detect_negation_mismatch(answer_text, matched_passages)
        if neg_mismatch and neg_note:
            audit_notes.append(neg_note)

        has_contradictions, contra_notes = detect_contradictory_evidence(retrieved_passages)
        if has_contradictions:
            audit_notes.extend(contra_notes)

        entail_score = compute_entailment_score(answer_text, matched_passages)

        return CitationVerificationResult(
            epistemic_status=status,
            grounding_score=round(grounding_score, 4),
            total_citations_found=len(citations_matches),
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            cited_passages=matched_passages,
            is_verified=is_verified,
            audit_notes=audit_notes,
            has_contradictory_evidence=has_contradictions,
            negation_mismatch=neg_mismatch,
            entailment_score=entail_score,
        )
