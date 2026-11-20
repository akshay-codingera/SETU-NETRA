"""
synthesizer.py: Evidence-backed context packaging and prompt synthesis for SETU-NETRA.

Why this file exists:
Downstream Large Language Models (LLMs) and Small Language Models (SLMs) must receive
reconstructed document context that is bounded within strict token budgets and annotated
with exact provenance tags. This prevents hallucinations, reduces token costs, and ensures
that every downstream generation can cite specific source documents, pages, and bounding boxes.
"""

from typing import Dict, List, Optional, Sequence, Tuple
from setu_netra.core.contracts import RetrievedPassage, SynthesizedContext


def estimate_token_count(text: str) -> int:
    """Fast, model-independent token count estimation.

    In standard English/code text, 1 token is approximately 3.8-4.0 characters.
    We use max(len(words), round(len(chars) / 3.8)) for a safe upper bound.
    """
    if not text:
        return 0
    char_estimate = int(len(text) / 3.8)
    word_estimate = int(len(text.split()) * 1.3)
    return max(char_estimate, word_estimate, 1)


class EvidenceContextSynthesizer:
    """Assembles retrieved document passages into token-budgeted, evidence-tagged prompt payloads."""

    SYSTEM_INSTRUCTION = (
        "You are an evidence-grounded AI assistant. Answer the user request strictly using "
        "the provided context evidence blocks below. Every assertion must cite its source "
        "in the exact format [Doc: <name>, Page: <p>, Block: <b>]. If the provided context "
        "does not contain sufficient evidence to answer, explicitly state that the answer "
        "cannot be verified from the uploaded documents rather than making assumptions."
    )

    def __init__(self, default_budget_tokens: int = 1500):
        self.default_budget_tokens = default_budget_tokens

    def synthesize(
        self,
        query: str,
        passages: Sequence[RetrievedPassage],
        max_budget_tokens: Optional[int] = None,
        custom_system_instruction: Optional[str] = None,
    ) -> SynthesizedContext:
        """Format retrieved passages into a structured, budget-enforced context prompt.

        Args:
            query: The user or system question/query.
            passages: Sequence of RetrievedPassage objects ranked by relevance.
            max_budget_tokens: Maximum allowed token budget for the context prompt.
            custom_system_instruction: Optional custom system instructions.

        Returns:
            SynthesizedContext containing the prompt and provenance metadata.
        """
        budget = max_budget_tokens or self.default_budget_tokens
        sys_inst = custom_system_instruction or self.SYSTEM_INSTRUCTION

        # Base header & footer
        header = (
            f"{sys_inst}\n\n"
            f"USER QUERY:\n{query.strip()}\n\n"
            f"VERIFIED CONTEXT EVIDENCE:\n"
            f"{'=' * 70}\n"
        )
        footer = (
            f"{'=' * 70}\n"
            f"INSTRUCTION: Synthesize your answer strictly based on the evidence blocks above.\n"
        )

        base_tokens = estimate_token_count(header)
        footer_tokens = estimate_token_count(footer)
        current_tokens = base_tokens + footer_tokens + 5  # Include template overhead in budget

        included_passages: List[RetrievedPassage] = []
        context_blocks: List[str] = []
        truncated = False

        for idx, p in enumerate(passages, start=1):
            box_str = f"({p.bounding_box[0]:.1f}, {p.bounding_box[1]:.1f}, {p.bounding_box[2]:.1f}, {p.bounding_box[3]:.1f})"
            block_text = (
                f"[EVIDENCE BLOCK {idx}]\n"
                f"Source: {p.document_name} | Page: {p.page_number} | Block: {p.block_id} | "
                f"Type: {p.block_type} | Conf: {p.confidence * 100:.1f}% | Box: {box_str}\n"
                f"Content:\n{p.text.strip()}\n"
                f"{'-' * 70}\n"
            )
            block_tokens = estimate_token_count(block_text)

            if current_tokens + block_tokens > budget:
                truncated = True
                break

            included_passages.append(p)
            context_blocks.append(block_text)
            current_tokens += block_tokens

        if len(passages) > len(included_passages):
            truncated = True

        if not context_blocks:
            body = "(No relevant context passages met the confidence threshold or token budget.)\n"
        else:
            body = "\n".join(context_blocks)

        full_context = f"{header}\n{body}\n{footer}"
        total_tokens = estimate_token_count(full_context)


        return SynthesizedContext(
            query=query,
            passages=tuple(included_passages),
            formatted_context=full_context,
            token_count_estimate=total_tokens,
            max_budget_tokens=budget,
            truncated=truncated,
            metadata={
                "passages_provided": len(passages),
                "passages_included": len(included_passages),
                "system_instruction_tokens": estimate_token_count(sys_inst),
            },
        )
