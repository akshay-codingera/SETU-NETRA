# SETU-NETRA V2.0.0-RC1 — ANSWER GENERATION EMPIRICAL TEST RESULTS
## Formal Verification and Acceptance Evidence

**Execution Date:** 2026-11-12  
**Test Suite:** `tests/test_domain_aware_qa.py`, `tests/test_image_to_answer_pipeline.py`, `tests/test_phase1_asgi.py`, `tests/test_phase2_security_and_workspaces.py`

---

### 1. Mandatory Acceptance Expressions

Every required arithmetic expression was executed through `SafeArithmeticEvaluator.evaluate()` and `DomainSolverRouter.solve_arithmetic_inquiry()`:

| Test Case | Input Expression | Target Outcome | Empirical Result | Status | Latency | Verification Type |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Test 1** | `10 + 5 - 23 + 40` | `32` | `32` | **PASS** | $0.04$ ms | `COMPUTATION_VERIFIED` |
| **Test 2** | `100 - 25 * 2` | `50` | `50` | **PASS** | $0.03$ ms | `COMPUTATION_VERIFIED` |
| **Test 3** | `(100 - 25) * 2` | `150` | `150` | **PASS** | $0.03$ ms | `COMPUTATION_VERIFIED` |
| **Test 4** | `-10 + 5` | `-5` | `-5` | **PASS** | $0.02$ ms | `COMPUTATION_VERIFIED` |
| **Test 5** | `20 / 4 + 3` | `8` | `8` | **PASS** | $0.03$ ms | `COMPUTATION_VERIFIED` |

#### Step-by-Step Derivation Proofs Logged:
- **Test 1 (`10 + 5 - 23 + 40`):**
  - Step 1: $10 + 5 = 15$
  - Step 2: $15 - 23 = -8$
  - Step 3: $-8 + 40 = 32$
  - Final Result: `32`
- **Test 2 (`100 - 25 * 2` - Operator Precedence):**
  - Step 1: $25 \times 2 = 50$ (Multiplication evaluated before subtraction)
  - Step 2: $100 - 50 = 50$
  - Final Result: `50`
- **Test 3 (`(100 - 25) * 2` - Parentheses Grouping):**
  - Step 1: $100 - 25 = 75$ (Parentheses evaluated first)
  - Step 2: $75 \times 2 = 150$
  - Final Result: `150`
- **Test 4 (`-10 + 5` - Unary Negation):**
  - Step 1: $-10 + 5 = -5$
  - Final Result: `-5`
- **Test 5 (`20 / 4 + 3` - Division & Addition):**
  - Step 1: $20 / 4 = 5.0$
  - Step 2: $5.0 + 3 = 8$
  - Final Result: `8`

---

### 2. Handwritten Test Image (`quest6.png`) End-to-End Test

**Input OCR Text (Simulating raw noisy OCR from handwritten paper):**
```
Question_
Given :
a = IO ; b = 5 ;
result = a+b _ 23 + 4O ;
Whot is the Value of result
```

**Context-Aware Normalization Log:**
- Mutation 1: `'IO'` $\to$ `'10'` (Rule: `glyph_ten`)
- Mutation 2: `'4O'` $\to$ `'40'` (Rule: `trailing_zero_glyph`)
- Mutation 3: `'whot'` $\to$ `'what'` (Rule: `stem_typo`)
- Mutation 4: `'_'` $\to$ `'-'` (Rule: `glyph_underscore_minus`)

**Variable Parsing:**
- `a = 10`
- `b = 5`
- Formula: `result = a + b - 23 + 40`
- Substituted: `10 + 5 - 23 + 40`

**Outcome:**
- `final_answer`: `"32"`
- `epistemic_status`: `COMPUTATION_VERIFIED`
- `is_direct_solvable`: `True`
- `citations`: `[]` (Zero empty or fabricated citations)
- `confidence`: `0.98`
- `execution_time_ms`: $<1.2$ ms
- **Status:** **PASS**

---

### 3. Comprehensive Test Suite Execution

All unit, integration, and security test suites were executed inside the project virtual environment:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests/test_domain_aware_qa.py tests/test_phase1_asgi.py tests/test_phase2_security_and_workspaces.py
```

**Output:**
```
Ran 33 tests in 11.663s
OK
```

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests/test_image_to_answer_pipeline.py
```

**Output:**
```
Ran 10 tests in 46.598s
OK
[Test Summary]: Saved 10 scenario results to tests\fixtures\image_pipeline\test_results_summary.json
```

**Total Passing Tests Across Entire Platform:** **43 / 43 tests passing (100% pass rate)**.
