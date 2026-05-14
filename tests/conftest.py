"""Test import compatibility for the current source layout."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

for relative in (
    "src/calc",
    "src/trading",
    "src/swqos",
    "src/middleware",
    "src/serialization",
    "src/compute",
    "src/execution",
    "src/hotpath",
    "src/common",
):
    path = str(ROOT / relative)
    if path not in sys.path:
        sys.path.insert(0, path)

