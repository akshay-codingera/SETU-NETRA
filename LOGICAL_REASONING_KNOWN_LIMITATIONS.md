# Known Limitations: Logical Reasoning & Formal Deduction

**Document Version:** 1.0.0  
**Subsystem:** `src/setu_netra/qa/domain_router.py` (Logical Reasoning Engine)  
**Date:** November 12, 2026  

---

## 1. Domain Coverage Boundaries

1. **Classical Categorical vs First-Order Predicate Logic with Relations:**
   The current deterministic engine specializes in Aristotelian and monadic categorical syllogisms involving class inclusion, intersection, and disjointness ($A \subseteq B$, $A \cap B \neq \emptyset$, $A \cap B = \emptyset$). Problems requiring multi-place polyadic predicates (e.g. *"Every person loves someone who respects all teachers"*) or mathematical induction exceed categorical countermodel evaluation and fall back to grounded generative reasoning.

2. **Temporal & Dynamic Logics:**
   Syllogisms with time-varying states (*"Before X happens, Y always holds, but after Z, Y ceases"*) cannot be represented as static categorical sets and require Linear Temporal Logic (LTL) modeling.

3. **Probability & Credence Weightings:**
   The syllogism solver operates on exact deductive truth values (`DEFINITELY_TRUE`, `POSSIBLY_TRUE`, `DEFINITELY_FALSE`). Probabilistic statements (*"There is an 80% chance that a programmer is creative"*) are not supported under Aristotelian syllogism rules.

---

## 2. Handwriting & Semantic Nuances

1. **Double Negatives in Natural Language:**
   Handwritten inquiries with nested rhetorical double negatives (*"It is not untrue that no programmers are non-logical"*) require careful syntactic decomposition to avoid inversion errors.

2. **Existential Import Assumptions:**
   In classical Aristotelian logic, universal statements ($All\ S\ are\ P$) traditionally carry existential import ($S \neq \emptyset$). In modern mathematical Boolean logic, universal statements are vacuously true when the antecedent set is empty ($S = \emptyset$). The SETU-NETRA prover explicitly clarifies whether existential non-emptiness is assumed when evaluating modal conclusions like *"may be"*.
