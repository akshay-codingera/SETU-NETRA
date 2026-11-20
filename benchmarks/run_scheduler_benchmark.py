"""
run_scheduler_benchmark.py: CLI entry point for Stage 6 scheduler microbenchmarking.

Usage:
    python benchmarks/run_scheduler_benchmark.py [--repetitions 3] [--requests-per-rep 25]
"""

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.runners.scheduler_runner import SchedulerBenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="Run SETU-NETRA Scheduler Microbenchmarks")
    parser.add_argument("--repetitions", type=int, default=3, help="Number of independent evaluation repetitions")
    parser.add_argument("--requests-per-rep", type=int, default=25, help="Number of requests per repetition")
    args = parser.parse_args()

    runner = SchedulerBenchmarkRunner()
    runner.execute_full_suite(
        repetition_count=args.repetitions,
        requests_per_rep=args.requests_per_rep,
    )


if __name__ == "__main__":
    main()
