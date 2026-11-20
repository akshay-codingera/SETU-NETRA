"""
Convenience entrypoint script for Milestone 1.

Usage:
    python run_milestone1.py --image path/to/image.jpg
"""

import sys
from pathlib import Path

# Add src to Python search path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.cli.process_image import main

if __name__ == "__main__":
    sys.exit(main())
