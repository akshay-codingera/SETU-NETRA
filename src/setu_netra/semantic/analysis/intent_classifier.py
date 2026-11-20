"""
intent_classifier.py: Multi-intent question classification for academic queries.

Why this file exists:
Determines what actions or responses a question demands (e.g. calculation, complexity analysis,
derivation, definition, comparison, proof, or identification). Supports compound multi-intent
queries without relying exclusively on the leading sentence verb.
"""

import re
from typing import List, Set, Tuple
from setu_netra.core.contracts import QuestionIntent


INTENT_PATTERNS: List[Tuple[str, str, int]] = [
    # Complexity Analysis
    (
        QuestionIntent.COMPLEXITY_ANALYSIS,
        r"\b(computational complexity|time complexity|space complexity|running[- ]time|asymptotic bound|big[- ]o|worst[- ]case runtime|how long does [^?]+ take)\b",
        10,
    ),
    # Multiple Choice Selection
    (
        QuestionIntent.MULTIPLE_CHOICE_SELECTION,
        r"\b(which of the following|choose the correct|select the best|\[[A-D]\]|[A-D]\))\b",
        8,
    ),
    # Comparison
    (
        QuestionIntent.COMPARISON,
        r"\b(compare|contrast|difference between|versus|distinguish between)\b",
        8,
    ),
    # Proof
    (
        QuestionIntent.PROOF,
        r"\b(prove that|proof|show by induction|show that for all|disprove)\b",
        9,
    ),
    # Derivation
    (
        QuestionIntent.DERIVATION,
        r"\b(derive|derivation|show step by step how to obtain|deduce the formula)\b",
        8,
    ),
    # Calculation / Computation
    (
        QuestionIntent.CALCULATION,
        r"\b(calculate|compute|evaluate the expression|find the exact value|how many)\b",
        7,
    ),
    # Definition
    (
        QuestionIntent.DEFINITION,
        r"\b(define|what is meant by|give the definition of|state the definition|definition of)\b",
        7,
    ),
    # Explanation
    (
        QuestionIntent.EXPLANATION,
        r"\b(explain|discuss|describe|why does|how does)\b",
        6,
    ),
    # Identification
    (
        QuestionIntent.IDENTIFICATION,
        r"\b(who is|name the|identify the|which protocol|which country|which person|who was)\b",
        6,
    ),
    # Code Generation & Implementation
    (
        QuestionIntent.CODE_GENERATION,
        r"\b(write a python|implement a function|write a program|write code to)\b",
        8,
    ),
    # Debugging
    (
        QuestionIntent.DEBUGGING,
        r"\b(find the bug|debug|correct the error|fix the issue|identify the mistake)\b",
        8,
    ),
]


def classify_question_intents(text: str, has_options: bool = False) -> List[str]:
    """Classify communicative intents of an academic question.

    Args:
        text: Reconstructed question text.
        has_options: True if multiple choice answer options [A, B, ...] are attached.

    Returns:
        List of intent strings (can contain multiple intents for compound tasks).
    """
    cleaned = text.strip()
    if not cleaned:
        return [QuestionIntent.UNKNOWN]

    matched_intents: List[str] = []
    lower_text = cleaned.lower()

    for intent, pattern, _ in INTENT_PATTERNS:
        if re.search(pattern, lower_text):
            if intent not in matched_intents:
                matched_intents.append(intent)

    # Attach MULTIPLE_CHOICE_SELECTION if question has structural answer options
    if has_options and QuestionIntent.MULTIPLE_CHOICE_SELECTION not in matched_intents:
        matched_intents.append(QuestionIntent.MULTIPLE_CHOICE_SELECTION)

    # Fallback to general question starters if no specific pattern matched
    if not matched_intents:
        if lower_text.startswith("what is") or lower_text.startswith("what are"):
            matched_intents.append(QuestionIntent.DEFINITION)
        elif lower_text.startswith("how to") or lower_text.startswith("how do"):
            matched_intents.append(QuestionIntent.EXPLANATION)
        elif lower_text.startswith("who is"):
            matched_intents.append(QuestionIntent.IDENTIFICATION)
        elif "?" in cleaned:
            matched_intents.append(QuestionIntent.OTHER)
        else:
            matched_intents.append(QuestionIntent.UNKNOWN)

    return matched_intents
