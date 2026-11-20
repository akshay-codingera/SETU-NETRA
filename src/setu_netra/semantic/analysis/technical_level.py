"""
technical_level.py: Academic technical depth assessment for document content.

Why this file exists:
Evaluates the conceptual and mathematical sophistication of text without making
unsupported claims about the author's personal identity or education level.
Categorizes content into INTRODUCTORY, INTERMEDIATE, ADVANCED, or RESEARCH_ORIENTED.
"""

import re
from typing import Set
from setu_netra.core.contracts import TechnicalLevel


ADVANCED_JARGON: Set[str] = {
    "asymptotic", "eigenvalue", "eigenvector", "singular value decomposition",
    "np-complete", "hilbert space", "homomorphism", "concomitant", "isomorphism",
    "stochastic", "convex optimization", "backpropagation", "tensor", "vinculum",
}

INTERMEDIATE_JARGON: Set[str] = {
    "complexity", "convolution", "big-o", "matrix", "derivative", "integral",
    "protocol", "relational", "normalization", "encryption", "hashing", "variance",
    "stride", "hypothesis", "tree", "pointer", "polynomial",
}

INTRODUCTORY_INDICATORS: Set[str] = {
    "who is", "what is", "capital of", "prime minister", "president",
    "how many", "basic", "simple", "everyday", "name the",
}


def estimate_technical_level(text: str) -> str:
    """Estimate the technical depth of academic text based on lexical sophistication.

    Args:
        text: Reconstructed text string.

    Returns:
        One of TechnicalLevel enum strings.
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned.split()) < 3:
        return TechnicalLevel.UNKNOWN

    lower = cleaned.lower()
    words = set(re.findall(r"[a-z0-9_\-]+", lower))

    adv_matches = len(words.intersection(ADVANCED_JARGON))
    int_matches = len(words.intersection(INTERMEDIATE_JARGON))
    intro_matches = any(phrase in lower for phrase in INTRODUCTORY_INDICATORS)

    # Check for formal mathematical notation or derivation/proof framing
    has_math_symbols = bool(re.search(r"[∑∫∂λ∈∀∃≤≥√]", text))
    has_big_o = bool(re.search(r"\bO\s*\(", text))
    has_formal_framing = any(w in words for w in ("bound", "derive", "derivation", "proof", "theorem", "tensor"))

    if adv_matches >= 2 or (adv_matches >= 1 and (has_math_symbols or has_formal_framing)):
        return TechnicalLevel.ADVANCED

    if has_big_o or int_matches >= 2 or (int_matches >= 1 and "size" in words):
        return TechnicalLevel.INTERMEDIATE

    if intro_matches and int_matches == 0 and adv_matches == 0 and not has_big_o:
        return TechnicalLevel.INTRODUCTORY

    if int_matches >= 1:
        return TechnicalLevel.INTERMEDIATE

    return TechnicalLevel.INTRODUCTORY
