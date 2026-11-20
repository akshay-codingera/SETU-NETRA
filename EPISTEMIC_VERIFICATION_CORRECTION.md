# SETU-NETRA V2.0.0-RC1 — EPISTEMIC VERIFICATION CORRECTION
## Policy Separation, Grounding Rules, and Citation Integrity

**Module:** `src/setu_netra/qa/engine.py`, `src/setu_netra/qa/domain_router.py`, `frontend/src/views/QuestionAnsweringView.tsx`

---

### 1. The Epistemic Grounding Problem

In previous versions, SETU-NETRA enforced a singular verification policy across all queries:
> *"Every answer must have one or more document bounding-box citations with high lexical/semantic overlap, or it shall be marked UNSUPPORTED."*

This rule is valid for **empirical claims** (e.g. historical dates, policy statements, experimental parameters). However, applying it to **logical and mathematical deductions** produced two severe defects:
1. **False Rejection:** Valid arithmetic evaluations were rejected as `UNSUPPORTED (Insufficient evidence)` simply because the problem image did not contain an explicit statement of the answer.
2. **Citation Fabrication & Empty Cards:** In attempts to satisfy the citation verifier, empty strings `""` or entire question blocks were cited as "evidence" for the calculation, displaying confusing `Score: Verified` badges next to empty quotes.

---

### 2. Domain-Specific Epistemic Policies

SETU-NETRA v2.0.0-RC1 establishes explicit epistemic verification types tailored to the cognitive nature of each problem:

```
                                 Verification Policy Matrix
┌───────────────────────┬───────────────────────────────┬────────────────────────────────────────┐
│ Status                │ Grounding Criterion           │ Citation Requirement                   │
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ COMPUTATION_VERIFIED  │ Deterministic AST evaluation  │ citations = []                         │
│                       │ and operator precedence steps │ (Mathematical proof, NO fake citations)│
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ LOGIC_VERIFIED        │ Relational logic, AST code,   │ citations = [] or relational clauses   │
│                       │ or syntax validation          │                                        │
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ FORMULA_VERIFIED      │ Standard mathematical formula │ Formula derivation and parameters      │
│                       │ or complexity proof           │                                        │
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ EVIDENCE_BACKED       │ Lexical/semantic grounding in │ Non-empty bounding box citations with   │
│                       │ corpus document blocks        │ factual support score >= threshold     │
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ GENERAL_KNOWLEDGE     │ Model parameter knowledge     │ citations = []                         │
│                       │ (external to corpus)          │ (Explicit transparency disclosure)     │
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ NEEDS_CLARIFICATION   │ Low OCR confidence or missing │ citations = []                         │
│                       │ operator/variable definitions │ (Prompts user to review extracted text)│
├───────────────────────┼───────────────────────────────┼────────────────────────────────────────┤
│ UNSUPPORTED           │ Empirical query with no       │ citations = []                         │
│                       │ supporting corpus passages    │                                        │
└───────────────────────┴───────────────────────────────┴────────────────────────────────────────┘
```

---

### 3. Strict Citation Integrity Rules

The engine now enforces four invariant rules:

1. **Zero Citation Fabrication:** Under NO circumstances may the engine generate a citation referencing a document block if that block merely poses the question rather than asserting the factual claim.
2. **Zero Empty Citations:** Any citation with empty text, whitespace, or missing bounding coordinates is pruned before serializing the response. Frontend filters (`citations.filter(c => c.text && c.text.trim().length > 0)`) ensure no empty cards render on the canvas.
3. **Proof as Provenance:** For `COMPUTATION_VERIFIED`, the provenance is the **mathematical derivation** (e.g., Step 1: Parse variables $\to$ Step 2: Substitute $\to$ Step 3: Evaluate following precedence).
4. **Document Association Disclosure:** When an arithmetic problem originates from an ingested document, the document name is recorded in `metadata["provenance_document"]`, providing auditability without fabricating a citation.

---

### 4. Frontend Visual Identity & Rendering

The presentation in `QuestionAnsweringView.tsx` and `DocumentIntelligenceView.tsx` reflects these rules according to Kora Kaagaz design principles:

- **Epistemic Seal Badge:**
  - `COMPUTATION_VERIFIED`: `#15803D` (Forest Green seal) with `Calculator` icon.
  - `LOGIC_VERIFIED`: `#7E22CE` (Ink Purple seal) with `Database` icon.
  - `EVIDENCE_BACKED`: `#047857` (Emerald seal) with `ShieldCheck` icon.
  - `GENERAL_KNOWLEDGE`: `#B45309` (Amber seal) with `BookOpen` icon.
  - `UNSUPPORTED`: `#B91C1C` (Crimson seal) with `AlertCircle` icon.
- **Reconstructed Question & Domain Banner:** Displays the classified domain and the sanitized question with confidence score.
- **Bold Verified Answer:** Displayed with high typographic contrast in `#1A1918` over `#FAF6EE` natural parchment.
- **Step-by-Step Derivation Card:** Explains every operator reduction step clearly, allowing students, researchers, and invigilators to trace the calculation.
- **Grounded Citations Container:** Renders only when genuine empirical document citations exist. For arithmetic, a clean deterministic verification notice is displayed instead.
