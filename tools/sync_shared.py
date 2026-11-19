#!/usr/bin/env python3
"""Copy shared/_godotx.py into every skills/*/scripts/ folder whose scripts import it.

Usage: python tools/sync_shared.py [--check]   (--check: exit 1 if any copy is stale)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "shared" / "_godotx.py"


def targets():
    for d in sorted((ROOT / "skills").glob("*/scripts")):
        if any(p.name != "_godotx.py" and re.search(r"^from _godotx import", p.read_text("utf-8"), re.M) for p in d.glob("*.py")):
            yield d / "_godotx.py"


def main():
    src = SRC.read_bytes()
    stale = [t for t in targets() if not t.exists() or t.read_bytes() != src]
    if "--check" in sys.argv:
        for t in stale:
            print(f"stale: {t.relative_to(ROOT)}")
        return 1 if stale else 0
    for t in stale:
        t.write_bytes(src)
        print(f"synced {t.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
