"""
Setu-Netra — Stage 7: Path Decision Engine (v0 prototype)
----------------------------------------------------------
Ties together:
  Stage 3 (Complexity Analyzer) -> complexity_classifier.classify()
  Stage 4 (Capability Matcher)  -> model_registry.match()
  Stage 5 (Cost Estimator)      -> estimate_cost() below (FrugalGPT-style: pay
                                    per token, minimize cost for target quality)

This is a pre-inference router (decide-then-serve), following RouteLLM's
approach rather than FrugalGPT's sequential try-then-escalate cascade —
though the Escalating Engine (Stage 11) can still kick in downstream if the
Output Validator (Stage 10) rejects a response.
"""

from dataclasses import dataclass, asdict
import json

from complexity_classifier import classify, ComplexityResult
from model_registry import match, ModelProfile


@dataclass
class RoutingDecision:
    prompt: str
    complexity: ComplexityResult
    model: ModelProfile
    estimated_tokens: int
    estimated_cost_usd: float
    estimated_latency_ms: int


def estimate_tokens(prompt: str) -> int:
    # crude token estimate: ~1.3 tokens per word, plus a fixed response budget
    words = len(prompt.split())
    prompt_tokens = int(words * 1.3)
    response_tokens = 150  # assumed average response length for estimation
    return prompt_tokens + response_tokens


def route(prompt: str) -> RoutingDecision:
    complexity = classify(prompt)
    model = match(complexity.tier)
    tokens = estimate_tokens(prompt)
    cost = round((tokens / 1000) * model.cost_per_1k_tokens, 6)

    return RoutingDecision(
        prompt=prompt,
        complexity=complexity,
        model=model,
        estimated_tokens=tokens,
        estimated_cost_usd=cost,
        estimated_latency_ms=model.avg_latency_ms,
    )


def route_to_dict(decision: RoutingDecision) -> dict:
    d = asdict(decision)
    return d


if __name__ == "__main__":
    prompts = [
        "What is the capital of France?",
        "Explain the difference between TCP and UDP.",
        "Design a distributed cache eviction algorithm and prove its amortized time complexity.",
    ]
    for p in prompts:
        decision = route(p)
        print(json.dumps(route_to_dict(decision), indent=2, default=str))
        print("-" * 60)
