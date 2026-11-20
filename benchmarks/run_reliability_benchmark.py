"""
run_reliability_benchmark.py: CLI entry point for Stage 6 reliability, circuit breaking, and resilience evaluation.

Usage:
    python benchmarks/run_reliability_benchmark.py
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.reliability_runner import ReliabilityBenchmarkRunner


def main():
    runner = ReliabilityBenchmarkRunner()
    runner.execute_all_reliability_tests()


if __name__ == "__main__":
    main()
