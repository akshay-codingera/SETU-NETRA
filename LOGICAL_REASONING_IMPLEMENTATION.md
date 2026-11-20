# Logical Reasoning Engine Implementation: Categorical Syllogisms & Countermodels

**Document Version:** 1.0.0  
**Subsystem:** `src/setu_netra/qa/domain_router.py` (`solve_logical_reasoning_inquiry`)  
**Date:** November 12, 2026  

---

## 1. Architectural Design

The Logical Reasoning Engine operates deterministically by formalizing categorical propositions into first-order set-theoretic predicates and testing candidate conclusions across all models that satisfy the problem premises.

```
Raw Handwritten Syllogism
        │
        ▼
Lexical Normalization ('crealive' -> 'creative', 'ihich' -> 'which')
        │
        ▼
Premise & Conclusion Parsing (Statements 1..3, Options A..D)
        │
        ▼
Model-Theoretic Countermodel Prover
  ├─ Universal Affirmative (A): S ⊆ P
  ├─ Particular Affirmative (I): S ∩ P ≠ ∅
  ├─ Universal Negative (E): S ∩ P = ∅
  └─ Modal Possibility ("may be"): ∃ M |= (S ∩ P ≠ ∅)
        │
        ▼
Deductive Necessity & Possibility Classification
        │
        ▼
LOGIC_VERIFIED Response Synthesis (citations: [])
```

---

## 2. Formal Proposition Engine

### 2.1 Standard Categorical Forms
Each premise and conclusion is parsed into one of four Aristotelian categorical propositions:
- **Type A (Universal Affirmative):** *"All S are P"* $\implies S \subseteq P$
- **Type E (Universal Negative):** *"No S is P"* $\implies S \cap P = \emptyset$
- **Type I (Particular Affirmative):** *"Some S are P"* $\implies S \cap P \neq \emptyset$
- **Type O (Particular Negative):** *"Some S are not P"* $\implies S \setminus P \neq \emptyset$
- **Type M (Modal Possibility):** *"Some S may be P"* $\implies \text{Satisfiable with premises}$

### 2.2 Countermodel Generation
To verify whether a conclusion $C$ is definitely true ($P_1, P_2, P_3 \models C$), the engine tests for the existence of a countermodel $M$ such that:
$$M \models P_1 \land P_2 \land P_3 \quad \text{and} \quad M \not\models C$$
If such a model exists, the conclusion is proven to be **NOT DEFINITELY TRUE** (`INVALID_ENTAILMENT`).

---

## 3. Integration with Epistemic Pipeline

In `src/setu_netra/qa/engine.py` and `src/setu_netra/qa/image_question_solver.py`:
1. **Pre-Routing:** Inquiries classified as `LOGICAL_REASONING` bypass vector retrieval.
2. **Epistemic Classification:**
   - Status: `LOGIC_VERIFIED`
   - Verification Method: `FORMAL_SET_THEORETIC_COUNTERMODEL`
   - Confidence: `0.98`
   - Citations: `[]` (Empty list; UI renders an explicit deductive proof note and suppresses empty citation cards).
3. **Telemetry & Audit:** Generates monotonic event ledger entry with verification proof trace.
