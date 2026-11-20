"""
Setu-Netra — Stage 3: Complexity Analyzer (v0 prototype)
----------------------------------------------------------
This is a first, heuristic-only version of the complexity classifier.
It scores an incoming prompt on a few cheap-to-compute signals and buckets
it into EASY / MEDIUM / HARD, in the spirit of RouteLLM's binary
weak/strong router but extended to 3 tiers.

This is intentionally NOT a trained model yet. It's here so the
end-to-end pipeline (classify -> route -> serve -> validate) has
something real to run against while the trained classifier
(BERT-based, per Stage 2/3 research) is built.
"""

from dataclasses import dataclass
import re

EASY = "EASY"
MEDIUM = "MEDIUM"
HARD = "HARD"

# Keywords that tend to correlate with harder reasoning / multi-step tasks
HARD_SIGNALS = [
    r"\bprove\b", r"\bderive\b", r"\bdesign\b", r"\barchitecture\b",
    r"\boptimi[sz]e\b", r"\btrade-?off\b", r"\bmulti-?step\b",
    r"\bwhy\b.*\bthen\b", r"\bcompare\b.*\bcontrast\b",
    r"\balgorithm\b", r"\bproof\b", r"\bderivative\b", r"\bintegral\b",
]

MEDIUM_SIGNALS = [
    r"\bexplain\b", r"\bsummari[sz]e\b", r"\banalyz[e]?\b",
    r"\bcompare\b", r"\bdifference between\b", r"\bhow does\b",
    r"\bwhat are the (pros|cons|benefits|drawbacks)\b",
]

EASY_SIGNALS = [
    r"^\s*(what is|who is|when is|where is)\b",
    r"\bdefine\b", r"\btranslate\b", r"\bconvert\b",
    r"\bcapital of\b", r"\bspell\b",
]


@dataclass
class ComplexityResult:
    tier: str
    score: float          # 0.0 (trivial) - 1.0 (very hard)
    signals_matched: list
    word_count: int
    reasoning: str


def _count_matches(text: str, patterns: list) -> list:
    hits = []
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            hits.append(p)
    return hits


def classify(prompt: str) -> ComplexityResult:
    text = prompt.strip()
    word_count = len(text.split())

    hard_hits = _count_matches(text, HARD_SIGNALS)
    medium_hits = _count_matches(text, MEDIUM_SIGNALS)
    easy_hits = _count_matches(text, EASY_SIGNALS)

    # Base score from length (longer prompts tend to carry more sub-tasks)
    length_score = min(word_count / 60.0, 1.0)  # saturates at 60 words

    # Weighted signal score
    signal_score = (
        0.6 * min(len(hard_hits) / 2.0, 1.0)
        + 0.3 * min(len(medium_hits) / 2.0, 1.0)
        - 0.4 * min(len(easy_hits) / 1.0, 1.0)
    )

    score = max(0.0, min(1.0, 0.5 * length_score + 0.5 * (signal_score + 0.5)))

    if hard_hits or score >= 0.66:
        tier = HARD
        reasoning = f"Hard-signal keywords matched: {hard_hits}" if hard_hits else "High composite score from length + phrasing"
    elif easy_hits and not medium_hits and word_count < 15:
        tier = EASY
        reasoning = f"Easy-signal keywords matched: {easy_hits}, short prompt ({word_count} words)"
    elif score <= 0.33:
        tier = EASY
        reasoning = "Low composite score — short, simple, factual-looking prompt"
    else:
        tier = MEDIUM
        reasoning = f"Medium-signal keywords matched: {medium_hits}" if medium_hits else "Composite score in medium band"

    return ComplexityResult(
        tier=tier,
        score=round(score, 3),
        signals_matched=hard_hits + medium_hits + easy_hits,
        word_count=word_count,
        reasoning=reasoning,
    )


if __name__ == "__main__":
    samples = [
        "What is the capital of France?",
        "Explain the difference between TCP and UDP.",
        "Design a distributed cache eviction algorithm and prove its amortized time complexity.",
    ]
    for s in samples:
        r = classify(s)
        print(f"\nPrompt: {s}\n -> tier={r.tier} score={r.score} reasoning={r.reasoning}")
