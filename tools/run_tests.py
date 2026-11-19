#!/usr/bin/env python3
"""Run the test suite against a real Godot 4.7 (.NET build for the C# tests).

Usage: python tools/run_tests.py [name-filter]     (GODOT_EXE overrides engine discovery)
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(ROOT / "tests" / "run_all.py"), *sys.argv[1:]]))
