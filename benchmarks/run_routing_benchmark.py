"""
run_routing_benchmark.py: CLI entry point for Stage 6 adaptive model routing evaluation.

Usage:
    python benchmarks/run_routing_benchmark.py
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.routing_runner import RoutingEvaluationRunner


def main():
    runner = RoutingEvaluationRunner()
    runner.evaluate_routing_dataset()


if __name__ == "__main__":
    main()
