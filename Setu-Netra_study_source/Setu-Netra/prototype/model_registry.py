"""
Setu-Netra — Stage 4: Capability Matcher (v0 prototype)
----------------------------------------------------------
A small static registry standing in for a real HELM/VHELM/MTEB-informed
capability matcher. Each entry represents a model tier available to route to,
with mock cost/latency numbers so the router has something realistic to
optimize against. Swap this for a live registry (pulling real pricing/latency
from provider APIs) once Stage 4 is built out properly.
"""

from dataclasses import dataclass


@dataclass
class ModelProfile:
    name: str
    tier: str                 # which complexity tier this model is meant for
    cost_per_1k_tokens: float  # USD, illustrative only
    avg_latency_ms: int
    notes: str


MODEL_REGISTRY = [
    ModelProfile(
        name="small-local-model (e.g. Llama-3-8B class)",
        tier="EASY",
        cost_per_1k_tokens=0.0002,
        avg_latency_ms=120,
        notes="Cheap, fast, good enough for factual/short queries",
    ),
    ModelProfile(
        name="mid-tier-api-model (e.g. GPT-4o-mini / Claude Haiku class)",
        tier="MEDIUM",
        cost_per_1k_tokens=0.002,
        avg_latency_ms=400,
        notes="Balanced cost/quality for explanation & comparison tasks",
    ),
    ModelProfile(
        name="frontier-model (e.g. GPT-4o / Claude Opus class)",
        tier="HARD",
        cost_per_1k_tokens=0.03,
        avg_latency_ms=1200,
        notes="Reserved for multi-step reasoning, proofs, design tasks",
    ),
]


def match(tier: str) -> ModelProfile:
    for m in MODEL_REGISTRY:
        if m.tier == tier:
            return m
    # fallback to the strongest model if tier is unrecognized
    return MODEL_REGISTRY[-1]
