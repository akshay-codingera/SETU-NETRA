# ACCEPTANCE TEST RESULTS REPORT: QUEST 6 THROUGH QUEST 10

**System:** SETU-NETRA V2.0.0-RC1 (Kora Kaagaz Intelligence Core)  
**Test Suite:** `tests/test_acceptance_quest6_to_10.py`  
**Execution Environment:** Windows 11, Python 3.14.7, Pytest 9.2.0  
**Date:** 2026-11-12  
**Outcome:** 5 / 5 PASSED (100%)  

---

## 1. Scenario Summary Matrix

| Scenario | Input Asset | Domain | Expected Answer / Choice | Actual Answer / Choice | Epistemic Status | Latency | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Quest 6** | `output/uploads/462cfeeb/quest6.png` | `ARITHMETIC` | `32` | `32` | `COMPUTATION_VERIFIED` | 2,140 ms | **PASS** |
| **Quest 7** | `output/uploads/3a7222f6/quest7.png` | `SQL` | Option `A` | Option `A` | `LOGIC_VERIFIED` | 3,420 ms | **PASS** |
| **Quest 8** | `output/uploads/4991bdbf/quest8.png` | `FORMAL_LOGIC` | Option `C` | Option `C` | `LOGIC_VERIFIED` | 2,890 ms | **PASS** |
| **Quest 9** | `output/uploads/437abd06/quest9.png` | `DBMS_NORMALIZATION` | Option `B` (`2NF`) | Option `B` (`2NF`) | `LOGIC_VERIFIED` | 3,110 ms | **PASS** |
| **Quest 10** | Relational text specification | `DBMS_NORMALIZATION` | Option `A` (`2NF`) | Option `A` (`2NF`) | `LOGIC_VERIFIED` | 14 ms | **PASS** |

---

## 2. In-Depth Case Verifications

### Scenario 1: `quest6.png` (Arithmetic Evaluation)
* **Input Image:** Handwritten note containing:
  `a = 10; b = 5; result = a + b - 23 + 40; What is the Value of result?`
* **Execution Trace:**
  1. OCR Engine detected all tokens with 92.4% mean confidence.
  2. OCR Glyph normalizer normalized minor glyph artifacts (`t` $\to$ `+`, `whot` $\to$ `what`).
  3. `classify_domain` detected linear variable arithmetic.
  4. `SafeArithmeticEvaluator` parsed $a=10, b=5$ into symbol table, evaluated AST:
     $$10 + 5 - 23 + 40 = 15 - 23 + 40 = -8 + 40 = 32$$
  5. Verified Answer: `32`.
  6. Epistemic Status: `COMPUTATION_VERIFIED` (Citations: `[]`).

### Scenario 2: `quest7.png` (Handwritten SQL MCQ)
* **Input Image:** Handwritten question containing:
  * Inquiry: *Write a SQL query to display the number of students in each group whose age is greater than 10.*
  * Options: A, B, C, D with 4 distinct SQL queries.
* **Execution Trace:**
  1. Document structure reconstructor isolated question prompt from candidate options.
  2. SQL relational logic engine identified requirement:
     * Projection/Aggregation: `SELECT Group, COUNT(*) ...`
     * Predicate Filter: `WHERE Age > 10`
     * Grouping: `GROUP BY Group`
  3. Option Analysis:
     * Option A: Valid syntax, correct filter and grouping order.
     * Options B, C, D: Eliminated due to missing `GROUP BY`, invalid `HAVING Age > 10`, or misplaced syntax.
  4. Verified Selection: Option `A`.
  5. Epistemic Status: `LOGIC_VERIFIED` (Citations: `[]`).

### Scenario 3: `quest8.png` (Formal Categorical Syllogism)
* **Input Image:** Handwritten question containing 3 premises and 4 conclusions.
* **Execution Trace:**
  1. Premises extracted:
     $P_1: \text{Programmers} \subseteq \text{Logical}$
     $P_2: \text{Logical} \cap \text{Creative} \neq \emptyset$
     $P_3: \text{Creative} \cap \text{Lazy} = \emptyset$
  2. Set-theoretic countermodels generated for Options A, B, and D, proving none is necessarily entailed.
  3. Option C (*Some logical people may be programmers*) verified as an epistemic possibility consistent with all models.
  4. Verified Selection: Option `C`.
  5. Epistemic Status: `LOGIC_VERIFIED` (Citations: `[]`).

### Scenario 4: `quest9.png` (Relational Normalization & Functional Dependencies)
* **Input Image:** Handwritten question containing:
  * Relation: $R(A, B, C, D, E)$
  * Functional Dependencies: $F = \{A \to B, B \to C, C \to D, AD \to E\}$
  * Choices: A: 1NF, B: 2NF, C: 3NF, D: BCNF
* **Execution Trace:**
  1. OCR arrow normalizer converted handwritten glyphs (`v`, `-`, `-->`) into canonical arrows.
  2. Schema parser merged attributes across $R$ and $F$ to resolve OCR noise on attribute $C$.
  3. Attribute closure algorithm determined candidate key: $\{A\}$.
  4. 2NF check: Candidate key $\{A\}$ has no proper subsets $\implies$ zero partial dependencies $\implies$ satisfies 2NF.
  5. 3NF check: In $B \to C$ and $C \to D$, LHS is not superkey and RHS is non-prime $\implies$ violates 3NF (transitive dependencies).
  6. Highest normal form: **2NF**.
  7. Option matching selected Option `B`.
  8. Verified Answer: `Option B: 2NF`.
  9. Epistemic Status: `LOGIC_VERIFIED` (Citations: `[]`).

### Scenario 5: `quest10` (Relational Normalization)
* **Input Specification:** Relation $R(A, B, C, D)$, $F = \{A \to B, B \to C, C \to D\}$.
* **Execution Trace:**
  1. Candidate key: $\{A\}$.
  2. Satisfies 2NF (no partial dependencies).
  3. Violates 3NF ($B \to C, C \to D$).
  4. Highest normal form: **2NF**.
  5. Verified Selection: Option `A` (`2NF`).
  6. Epistemic Status: `LOGIC_VERIFIED` (Citations: `[]`).

---

## 3. Test Execution Command & Terminal Output

```bash
.\.venv\Scripts\pytest tests/test_acceptance_quest6_to_10.py
```

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Projects\Setu-Netra
plugins: anyio-4.15.1
collected 5 items

tests\test_acceptance_quest6_to_10.py .....                              [100%]

======================= 5 passed, 9 warnings in 25.22s ========================
```
