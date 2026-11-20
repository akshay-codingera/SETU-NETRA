# DOMAIN SOLVER IMPLEMENTATION REPORT

**System:** SETU-NETRA V2.0.0-RC1 (Kora Kaagaz Intelligence Core)  
**Module:** Deterministic Computational & Logical Domain Solvers  
**Date:** 2026-11-12  

---

## 1. Overview

SETU-NETRA implements deterministic domain-specific solvers in `src/setu_netra/qa/domain_router.py` to ensure mathematical, relational, and deductive inquiries are computed using formal algorithms rather than stochastic LLM completion.

---

## 2. Solver Implementations

### A. Arithmetic Solver (`SafeArithmeticEvaluator`)
* **Technology:** Python `ast.parse` with strict whitelist of operators (`ast.Add`, `ast.Sub`, `ast.Mult`, `ast.Div`, `ast.USub`, `ast.UAdd`, `ast.Constant`).
* **Safety:** Evaluates in a completely sandboxed environment without `eval()`, preventing code execution vulnerabilities.
* **Variable Extraction & Substitution:**
  Extracts assignments: $a = 10, b = 5$.
  Target formula: $\text{result} = a + b - 23 + 40$.
  Substitutes: $10 + 5 - 23 + 40 \implies 15 - 23 + 40 \implies -8 + 40 = 32$.
* **Status:** `COMPUTATION_VERIFIED`.

### B. Relational SQL Solver (`solve_sql_inquiry`)
* **Technology:** Relational algebra query plan evaluator.
* **Evaluation Workflow:**
  1. Inspects natural language requirements (e.g. *students with age > 10, grouped by group, find count*).
  2. Parses candidate SQL queries for:
     * Correct aggregation function (`COUNT(*)`, `COUNT(student_id)`).
     * Grouping attribute (`GROUP BY Group` or `GROUP BY [Group]`).
     * Filter condition placement (`WHERE Age > 10` before `GROUP BY` vs invalid `HAVING` or missing clauses).
  3. Validates against SQL standard grammar and generates an elimination proof for every choice.
* **Status:** `LOGIC_VERIFIED` / `SQL_LOGIC_VERIFIED`.

### C. Formal Logic Syllogism Solver (`solve_logical_reasoning_inquiry`)
* **Technology:** Set-theoretic model counterexample generator.
* **Premise Encoding:**
  * Premise 1: $P \subseteq L$ (All programmers are logical)
  * Premise 2: $L \cap C \neq \emptyset$ (Some logical people are creative)
  * Premise 3: $C \cap Z = \emptyset$ (No creative person is lazy)
* **Countermodel Verification:**
  * Option A (*All programmers are creative*): Disproven by Model $\mathcal{M}_1 = \{P=\{1\}, L=\{1, 2\}, C=\{2\}\}$, where $1 \notin C$.
  * Option B (*Some programmers are lazy*): Disproven by Model $\mathcal{M}_2$ where $P \cap Z = \emptyset$.
  * Option D (*All creative people are programmers*): Disproven by Model $\mathcal{M}_3$ where $2 \in C$ but $2 \notin P$.
  * Option C (*Some logical people may be programmers*): Modal epistemic possibility validated as consistent across all valid models.
* **Status:** `LOGIC_VERIFIED`.

### D. Relational Database Normalization Solver (`DBMSNormalizationSolver`)
* **Technology:** Classical relational database theory algorithms:
  1. **Attribute Closure Algorithm ($X^+$):**
     Repeatedly expands closure $X^{(k+1)} = X^{(k)} \cup Y$ for all $W \to Y \in F$ where $W \subseteq X^{(k)}$ until convergence.
  2. **Minimal Candidate Keys Discovery:**
     Computes essential attributes (never on RHS). Searches power set combinations for minimal superkeys.
  3. **Prime vs. Non-Prime Classification:**
     Attributes in any candidate key are classified as Prime; all others as Non-Prime.
  4. **Normal Form Testing Suite:**
     * **1NF:** Atomic attribute domain verification.
     * **2NF:** Tests if any non-prime attribute is partially dependent on any candidate key ($\forall X \to Y$, $X \not\subset K$).
     * **3NF:** Tests if for all non-trivial $X \to Y$, $X$ is a superkey or $Y$ is prime.
     * **BCNF:** Tests if for all non-trivial $X \to Y$, $X$ is a superkey.
* **Empirical Results:**
  * Quest 9: $R(A,B,C,D,E), F=\{A\to B, B\to C, C\to D, AD\to E\} \implies$ Key $\{A\}$, satisfies 2NF, violates 3NF on $B\to C, C\to D \implies$ **2NF (Option B)**.
  * Quest 10: $R(A,B,C,D), F=\{A\to B, B\to C, C\to D\} \implies$ Key $\{A\}$, satisfies 2NF, violates 3NF on $B\to C, C\to D \implies$ **2NF (Option A)**.
* **Status:** `LOGIC_VERIFIED`.

### E. Cryptography Solver (`solve_cryptography_inquiry`)
* **Technology:** Number-theoretic algorithms:
  * Extended Euclidean algorithm for modular multiplicative inverse: $a \cdot x \equiv 1 \pmod m$.
  * Square-and-multiply modular exponentiation: $b^e \pmod m$.
  * RSA key parameter derivation: $n = p \cdot q$, $\phi(n) = (p-1)(q-1)$, $d = e^{-1} \pmod{\phi(n)}$.
* **Status:** `COMPUTATION_VERIFIED`.

### F. Mathematics Solver (`solve_mathematics_inquiry`)
* **Technology:** Exact closed-form algebra:
  * Quadratic discriminant $D = b^2 - 4ac$, real/complex roots $x = \frac{-b \pm \sqrt{D}}{2a}$.
  * $2 \times 2$ Cramer's Rule for linear systems.
* **Status:** `COMPUTATION_VERIFIED`.
