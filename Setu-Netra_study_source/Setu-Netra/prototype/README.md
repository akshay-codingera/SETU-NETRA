# Setu-Netra — Prototype v0

This is the **first working slice** of the Setu-Netra pipeline: a runnable,
end-to-end path from a raw prompt to a routing decision, with cost estimation.

## What's implemented (v0)
- **`complexity_classifier.py`** — Stage 3 (Complexity Analyzer). Heuristic
  EASY/MEDIUM/HARD classifier based on keyword signals + prompt length.
  This is a placeholder for the trained BERT-based classifier described in
  the research plan — it exists so the rest of the pipeline has something
  real to run against today.
- **`model_registry.py`** — Stage 4 (Capability Matcher). Static registry of
  3 model tiers (small/mid/frontier) with illustrative cost & latency
  numbers, standing in for a live HELM/VHELM/MTEB-informed registry.
- **`router.py`** — Stage 7 (Path Decision Engine) + Stage 5 (Cost
  Estimator). Pre-inference routing (RouteLLM-style: decide before calling
  any model), not FrugalGPT-style sequential cascading.
- **`demo.py`** — runs 9 sample prompts of varying difficulty through the
  full pipeline and compares total cost against an "always use the
  frontier model" baseline.

## Run it
```bash
python3 demo.py
```

## Result from the sample run
9 prompts (3 easy / 3 medium / 3 hard) → **~63% estimated cost reduction**
versus always routing to the frontier model, while hard prompts still get
the frontier model at full cost (no quality loss on the prompts that need it).

This is the same kind of cost-vs-quality argument FrugalGPT and RouteLLM make
in their papers — this prototype reproduces the shape of that result on a toy
scale, with mock models, to validate the pipeline design before wiring in
real APIs.

## What's NOT implemented yet (honest gaps)
- **Real model calls** — everything downstream of routing is currently a
  mock cost/latency estimate. No actual LLM API is being called yet.
- **Trained classifier** — Stage 3 is keyword heuristics, not the planned
  BERT/CLINC150-informed classifier.
- **Stage 1 (Input Analyzer)**, **Stage 6 (Load Analyzer)**,
  **Stage 8 (Scheduler)**, **Stage 9 (Model Serving)**,
  **Stage 10 (Output Validator)**, **Stage 11 (Escalating Engine)**,
  **Stage 12 (Monitoring)** — not built yet.

## Next steps
1. Replace the heuristic classifier with a fine-tuned BERT model trained on
   labeled easy/medium/hard examples (possibly bootstrapped from
   MMLU/GSM8K/BIG-bench difficulty tiers).
2. Wire `model_registry.py` to real provider APIs (start with 2-3 real
   models: one small, one mid, one frontier).
3. Add Stage 10 (Output Validator) — even a simple confidence/length/format
   check — so the Escalating Engine (Stage 11) has something to trigger on.
4. Replace mock cost numbers with real provider pricing.
5. Build a small evaluation set (20-30 labeled prompts) to measure
   classifier accuracy, not just run it on hand-picked examples.
