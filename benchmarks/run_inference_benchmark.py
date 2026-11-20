"""
run_inference_benchmark.py: CLI entry point for Stage 6 real AI model inference benchmarking.

Usage:
    python benchmarks/run_inference_benchmark.py
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.inference_runner import RealInferenceBenchmarkRunner


def main():
    runner = RealInferenceBenchmarkRunner()
    runner.execute_all_inference_benchmarks()


if __name__ == "__main__":
    main()
