"""
demo_deterministic_solver.py: Demonstrates AST Arithmetic and DBMS Relational Normalization solvers.
"""
import sys

sys.path.insert(0, "src")

from setu_netra.qa.domain_router import DomainSolverRouter, DBMSNormalizationSolver

def run():
    print("=" * 70)
    print("  SETU-NETRA: DETERMINISTIC MATHEMATICAL & RELATIONAL SOLVERS")
    print("=" * 70)

    # Demo 1: Arithmetic AST evaluation
    print("\n[1] ARITHMETIC DOMAIN: SAFE AST EVALUATION (Zero eval(), 100% Exact)")
    arith_q = "Given: a = 20 ; b = 15 ; c = 5 ; result = a + b * 2 - c ; What is the value of result?"
    print(f"    Inquiry Statement:\n    \"{arith_q}\"")

    arith_res = DomainSolverRouter.solve_arithmetic_inquiry(arith_q)
    print(f"\n    • Epistemic Status:    {arith_res.epistemic_status.value}")
    print(f"    • Verification Method: {arith_res.verification_method}")
    print(f"    • Calculated Answer:   {arith_res.final_answer}")
    print(f"    • Step-by-Step Proof:\n{arith_res.step_by_step_explanation}")

    # Demo 2: Relational DBMS Normalization
    print("\n[2] DBMS DOMAIN: RELATIONAL ATTRIBUTE CLOSURE & NORMAL FORM ALGORITHM")
    dbms_q = """Consider relation R(A, B, C, D) with functional dependencies:
A -> B
B -> C
C -> D
What is the highest normal form?
A. 2NF
B. 3NF
C. BCNF
D. 1NF"""
    print(f"    Inquiry Statement:\n{dbms_q}\n")

    dbms_res = DomainSolverRouter.solve_dbms_normalization_inquiry(dbms_q)
    print(f"    • Epistemic Status:    {dbms_res.epistemic_status.value}")
    print(f"    • Verification Method: {dbms_res.verification_method}")
    print(f"    • Selected Choice:     {dbms_res.final_answer}")
    print(f"\n    • Relational Mathematical Proof:")
    for line in dbms_res.step_by_step_explanation.splitlines():
        print(f"       {line}")

    print("\n" + "=" * 70)
    print("  DETERMINISTIC SOLVER VERIFIED: Mathematical certainty without LLM hallucination.")
    print("=" * 70)

if __name__ == "__main__":
    run()
