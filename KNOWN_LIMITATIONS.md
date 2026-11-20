# KNOWN LIMITATIONS AND OPERATIONAL BOUNDS

**System:** SETU-NETRA V2.0.0-RC1 (Kora Kaagaz Intelligence Core)  
**Date:** 2026-11-12  

---

## 1. OCR Engine & Visual Quality Bounds

1. **Extreme Low-Resolution Handwriting (< 15 DPI):**
   When handwriting has severe stroke erosion or pixel height below 10 pixels, EasyOCR character confidence drops below 0.35. In these instances, SETU-NETRA halts execution and transitions to `NEEDS_CLARIFICATION`, allowing the researcher to review and correct the noisy text via the live Review/Edit interface in Documents & Spatial.
2. **Severely Warped Documents:**
   While affine rotation ($\pm 15^\circ$) and perspective tilt are handled by Neighbor-Chain baseline tracking, nonlinear sheet warping (such as crumpled paper or extreme cylindrical curvature from opened books) may cause partial word boundary splitting. Flattening with document scanners is recommended.
3. **Complex Nested Mathematical Fractions:**
   Multi-level handwritten fractions with complex nested radicals (e.g. $\sqrt{\frac{\int x dx}{\sum y^2}}$) are transcribed as flat linear tokens by text OCR models. For advanced calculus, LaTeX-based OCR or explicit text review is advised.

---

## 2. Solver Scope & Cognitive Boundaries

1. **Relational Database Normalization:**
   * The deterministic DBMS solver covers 1NF, 2NF, 3NF, and BCNF via complete power-set minimal superkey discovery and attribute closures $X^+$.
   * Higher normal forms (4NF multi-valued dependencies and 5NF join dependencies) require explicit semantic hypergraph decomposition and are classified as advanced database topics.
2. **Formal Logic:**
   * The syllogism prover evaluates categorical syllogisms ($A, E, I, O$ propositions) and modal possibilities (*may be*).
   * First-order logic formulas with arbitrary nested existential/universal quantifier alternation ($\exists x \forall y \exists z$) beyond standard syllogistic forms are routed to model inference.
3. **Local Hardware Constraints:**
   * Local CPU execution with PyTorch EasyOCR and local Ollama Qwen 3.5 2B takes between 2 to 5 seconds per full-page image on a modern multi-core CPU.
   * Concurrent image OCR requests are bounded to prevent memory thrashing.

---

## 3. Epistemic Transparency Guarantees

* **Zero Hallucination Tolerance:** Factual assertions without verified coordinate citations are never falsely stamped `EVIDENCE BACKED`.
* **Deterministic Precedence:** Whenever a mathematical, logical, or relational query is identified, deterministic algorithms take strict precedence over LLM generative output.
* **Traceability:** Every response includes correlation IDs, verification methods, step-by-step derivations, and option elimination rationales.
