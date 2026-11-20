import sys
sys.path.insert(0, "src")
from pathlib import Path
from PIL import Image
import pytest

from setu_netra.ocr.easyocr_engine import EasyOCREngine
from setu_netra.structure.reconstructor import DocumentStructureReconstructor
from setu_netra.qa.image_question_solver import ImageQuestionSolver
from setu_netra.qa.domain_router import DomainSolverRouter, QuestionDomain, EpistemicVerificationType


@pytest.fixture(scope="module")
def solver():
    ocr = EasyOCREngine()
    rec = DocumentStructureReconstructor()
    return ImageQuestionSolver(ocr_engine=ocr, reconstructor=rec)


def test_quest6_arithmetic(solver):
    """quest6.png: Arithmetic evaluation result = a + b - 23 + 40 -> 32."""
    p = None
    for cand in [Path("output/uploads/462cfeeb/quest6.png"), Path("uploads/quest6.png")]:
        if cand.exists():
            p = cand
            break
    if not p:
        for f in Path(".").glob("**/quest6.png"):
            p = f
            break
    assert p is not None and p.exists(), "quest6.png not found"

    with Image.open(p) as img:
        sol = solver.solve_image(img.copy(), workspace_id="ws_pradeep")

    assert sol.domain in ("ARITHMETIC", "PROGRAMMING")
    assert "32" in str(sol.final_answer)
    assert sol.epistemic_status == "COMPUTATION_VERIFIED"
    assert "32" in sol.step_by_step_explanation


def test_quest7_sql_group_by(solver):
    """quest7.png: SQL Query with WHERE Age > 10, GROUP BY Group -> Option A."""
    p = None
    for cand in [Path("output/uploads/3a7222f6/quest7.png"), Path("uploads/quest7.png")]:
        if cand.exists():
            p = cand
            break
    if not p:
        for f in Path(".").glob("**/quest7.png"):
            p = f
            break
    assert p is not None and p.exists(), "quest7.png not found"

    with Image.open(p) as img:
        sol = solver.solve_image(img.copy(), workspace_id="ws_pradeep")

    assert sol.domain == "SQL"
    assert sol.selected_option == "A"
    assert sol.epistemic_status in ("LOGIC_VERIFIED", "SQL_LOGIC_VERIFIED")


def test_quest8_formal_logic_syllogism(solver):
    """quest8.png: Formal Syllogism -> None definitely true, Option C consistent modal possibility."""
    p = None
    for cand in [Path("output/uploads/4991bdbf/quest8.png"), Path("uploads/quest8.png")]:
        if cand.exists():
            p = cand
            break
    if not p:
        for f in Path(".").glob("**/quest8.png"):
            p = f
            break
    assert p is not None and p.exists(), "quest8.png not found"

    with Image.open(p) as img:
        sol = solver.solve_image(img.copy(), workspace_id="ws_pradeep")

    assert sol.domain in ("LOGICAL_REASONING", "FORMAL_LOGIC")
    assert sol.selected_option == "C"
    assert sol.epistemic_status == "LOGIC_VERIFIED"


def test_quest9_dbms_normalization(solver):
    """quest9.png: R(A,B,C,D,E), F={A->B, B->C, C->D, AD->E} -> Key A, 2NF -> Option B."""
    p = None
    for cand in [Path("output/uploads/437abd06/quest9.png"), Path("uploads/quest9.png")]:
        if cand.exists():
            p = cand
            break
    if not p:
        for f in Path(".").glob("**/quest9.png"):
            p = f
            break
    assert p is not None and p.exists(), "quest9.png not found"

    with Image.open(p) as img:
        sol = solver.solve_image(img.copy(), workspace_id="ws_akshay_butola")

    assert sol.domain == "DBMS_NORMALIZATION"
    assert "2NF" in str(sol.final_answer)
    assert sol.selected_option == "B"
    assert sol.epistemic_status == "LOGIC_VERIFIED"
    assert "Candidate Key" in sol.step_by_step_explanation


def test_quest10_dbms_normalization():
    """quest10: R(A,B,C,D), F={A->B, B->C, C->D} -> Key A, 2NF -> Option A."""
    text10 = """
    Consider relation R(A, B, C, D) with functional dependencies:
    F = { A -> B, B -> C, C -> D }
    What is the highest normal form that R satisfies?
    A. 2NF
    B. 3NF
    C. 1NF
    D. BCNF
    """
    sol10 = DomainSolverRouter.solve_dbms_normalization_inquiry(text10)
    assert sol10.domain == QuestionDomain.DBMS_NORMALIZATION
    assert sol10.selected_option == "A"
    assert "2NF" in sol10.final_answer
    assert sol10.epistemic_status == EpistemicVerificationType.LOGIC_VERIFIED
    assert sol10.metadata["highest_normal_form"] == "2NF"
    assert sol10.metadata["candidate_keys"] == [["A"]]
