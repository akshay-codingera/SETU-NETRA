# SETU-NETRA V2.0.0-RC1 — ANSWER GENERATION KNOWN LIMITATIONS
## Scope Boundaries, Failure Modes, and Mitigation Protocols

**Module:** `src/setu_netra/qa/domain_router.py`, `src/setu_netra/qa/image_question_solver.py`

---

### 1. Mathematical Expression Boundaries

The deterministic safe AST evaluator (`SafeArithmeticEvaluator`) is engineered specifically for direct arithmetic, operator reduction, and variable substitution. The table below delineates supported versus out-of-scope capabilities:

| Expression Class | Example | Status | Routing Destination / Handling |
| :--- | :--- | :---: | :--- |
| **Linear Arithmetic** | `10 + 5 - 23 + 40` | **Fully Supported** | `SafeArithmeticEvaluator` (Direct AST) |
| **Parentheses / Precedence** | `(100 - 25) * 2` | **Fully Supported** | `SafeArithmeticEvaluator` (Direct AST) |
| **Decimals & Negatives** | `-12.5 + 4.2 / 2` | **Fully Supported** | `SafeArithmeticEvaluator` (Direct AST) |
| **Variable Assignment** | `a = 10; b = 5; res = a + b` | **Fully Supported** | `DomainSolverRouter` (Substituter + AST) |
| **Integer & Floor Div** | `20 / 4`, `20 // 4` | **Fully Supported** | `SafeArithmeticEvaluator` (Guarded division) |
| **Algebraic Equation Solving** | $2x + 5 = 15$ | *Out of Scope (AST)* | Routed to `MATHEMATICS` (LLM inference) |
| **Simultaneous Equations** | $x + y = 10, x - y = 2$ | *Out of Scope (AST)* | Routed to `MATHEMATICS` (LLM inference) |
| **Quadratic / Polynomial Roots**| $x^2 - 4x + 4 = 0$ | *Out of Scope (AST)* | Routed to `MATHEMATICS` (LLM inference) |
| **Calculus / Differentiation** | $\frac{d}{dx}(x^3 + 2x)$ | *Out of Scope (AST)* | Routed to `MATHEMATICS` (LLM inference) |
| **Matrix Operations** | $\begin{bmatrix}1 & 2 \\ 3 & 4\end{bmatrix} \times \mathbf{v}$ | *Out of Scope (AST)* | Routed to `MATHEMATICS` (LLM inference) |

---

### 2. OCR Recognition Limits

1. **Extreme Cursive or Degraded Writing:** If handwriting is severely distorted such that numbers cannot be distinguished from letters (e.g. handwritten `5` mistaken for `S` with low confidence $<0.30$), the system flags the extraction as `NEEDS_CLARIFICATION`.
2. **Implicit Multiplication Without Operators:** Expressions written as `2(a + b)` or `2a` (where `*` is omitted) require formal algebraic tokenization; currently, explicit operators (`*` or standard programming notation) are preferred.
3. **Multi-Line LaTeX / Fraction Bars:** Two-dimensional vertical fraction bars ($\frac{a}{b}$) without horizontal bounding boxes are recognized as separate lines unless flattened or parenthesized.

---

### 3. Mitigation Protocols & Fallbacks

SETU-NETRA implements a three-tier defense-in-depth mitigation architecture:

```
                            Noisy Handwritten Image
                                       │
                                       ▼
                     [Tier 1: OCR Glyph Normalization]
                     Converts 'IO' -> '10', '4O' -> '40', '_' -> '-'
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          [Direct AST Evaluates]             [AST Syntax Fails]
          Returns COMPUTATION_VERIFIED                   │
          (Answer: 32)                                   ▼
                                            [Tier 2: Adaptive LLM Reasoning]
                                            Qwen 3.5 2B solves with step-by-step
                                            reasoning disclosure.
                                                         │
                                                         ▼
                                            [Tier 3: User Review / Edit Canvas]
                                            User edits noisy OCR text on canvas
                                            and clicks "Identify and Answer".
```

#### User Text Review Canvas
If automated OCR fails on ambiguous handwriting, the user is never stuck. In the `Documents & Spatial` panel:
1. Click **"Review / Edit"** in the Complete Extracted Text card.
2. Edit the raw OCR text directly in the monospace text area.
3. Click **"Identify and Answer Question"**.
4. The solver consumes the edited text immediately, executes deterministic AST reduction, and outputs the verified answer with $100\%$ precision.
