"""
run_qa_quality_benchmark.py: CLI entry point for Stage 6 Document QA and Citation verification evaluation.

Usage:
    python benchmarks/run_qa_quality_benchmark.py
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.qa_runner import DocumentQAEvaluationRunner


def main():
    runner = DocumentQAEvaluationRunner()
    runner.execute_qa_evaluation()


if __name__ == "__main__":
    main()
