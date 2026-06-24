#!/usr/bin/env python3
"""Run ablation unit checks (CI gate)."""
import subprocess
import sys

raise SystemExit(
    subprocess.call([sys.executable, "-m", "pytest", "tests/test_ablation.py", "-q"])
)
