"""
Setu-Netra — end-to-end prototype demo
----------------------------------------------------------
Runs a batch of sample prompts through the routing pipeline and compares
total estimated cost against an "always use the frontier model" baseline —
the same kind of comparison FrugalGPT/RouteLLM use to justify routing.

Run: python3 demo.py
"""

from router import route
from model_registry import MODEL_REGISTRY

SAMPLE_PROMPTS = [
    "What is the capital of France?",
    "Define photosynthesis.",
    "Translate 'good morning' to Spanish.",
    "Explain the difference between TCP and UDP.",
    "Summarize the causes of World War 1 in a few sentences.",
    "What are the pros and cons of microservices vs a monolith?",
    "Design a distributed cache eviction algorithm and prove its amortized time complexity.",
    "Derive the gradient of the cross-entropy loss function with respect to the logits.",
    "Compare and contrast TCP congestion control algorithms and propose an optimization for high-latency links.",
]

FRONTIER_MODEL = next(m for m in MODEL_REGISTRY if m.tier == "HARD")


def run():
    total_routed_cost = 0.0
    total_baseline_cost = 0.0
    tier_counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}

    print("=" * 78)
    print("SETU-NETRA — Adaptive AI Request Path Decider (prototype run)")
    print("=" * 78)

    for prompt in SAMPLE_PROMPTS:
        decision = route(prompt)
        tier_counts[decision.complexity.tier] += 1
        total_routed_cost += decision.estimated_cost_usd

        baseline_cost = round(
            (decision.estimated_tokens / 1000) * FRONTIER_MODEL.cost_per_1k_tokens, 6
        )
        total_baseline_cost += baseline_cost

        print(f"\nPROMPT: {prompt}")
        print(f"  -> complexity tier   : {decision.complexity.tier}  (score={decision.complexity.score})")
        print(f"  -> reasoning         : {decision.complexity.reasoning}")
        print(f"  -> routed to         : {decision.model.name}")
        print(f"  -> est. tokens       : {decision.estimated_tokens}")
        print(f"  -> est. cost (routed): ${decision.estimated_cost_usd:.6f}")
        print(f"  -> est. cost (always-frontier baseline): ${baseline_cost:.6f}")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"Total prompts run          : {len(SAMPLE_PROMPTS)}")
    print(f"Tier distribution          : {tier_counts}")
    print(f"Total cost (Setu-Netra)    : ${total_routed_cost:.6f}")
    print(f"Total cost (always-frontier): ${total_baseline_cost:.6f}")
    if total_baseline_cost > 0:
        savings_pct = 100 * (1 - total_routed_cost / total_baseline_cost)
        print(f"Estimated cost reduction   : {savings_pct:.1f}%")
    print("=" * 78)


if __name__ == "__main__":
    run()
