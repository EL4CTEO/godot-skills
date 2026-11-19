"""Test runner: discovers tests/test_*.py and runs each test_* function (no pytest needed).

Usage: python tests/run_all.py [name-filter]   (or: python tools/run_tests.py [name-filter])
Tests drive the real Godot 4.7 engine through the skill scripts. GODOT_EXE overrides discovery.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SKILLS = ROOT / "skills"
FIXTURES = HERE / "fixtures"
TMP = pathlib.Path(tempfile.mkdtemp(prefix="gas_tests_"))
GDUNIT_VERSION = "6.2.2"
sys.path.insert(0, str(SKILLS / "godot-core" / "scripts"))
import _godotx  # noqa: E402


class Skip(Exception):
    pass


def script(skill, name, *args, cwd=None, timeout=900, ok_codes=(0, 1)):
    """Run skills/<skill>/scripts/<name>.py with args; return its parsed JSON output."""
    p = subprocess.run([sys.executable, str(SKILLS / skill / "scripts" / f"{name}.py"), *map(str, args)],
                       cwd=str(cwd or ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith("{")), None)
    if line is None or p.returncode not in ok_codes:
        raise AssertionError(f"{skill}/{name} rc={p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return json.loads(line)


def fixture(name):
    """Fresh copy of tests/fixtures/<name> (without caches) in a temp dir."""
    dst = TMP / f"{name}_{time.time_ns()}"
    shutil.copytree(FIXTURES / name, dst, ignore=shutil.ignore_patterns(".godot", "bin", "obj", "reports"))
    return dst


def dotnet():
    exe = shutil.which("dotnet") or ("C:/Program Files/dotnet/dotnet.exe" if os.path.isfile("C:/Program Files/dotnet/dotnet.exe") else None)
    if not exe:
        raise Skip("no .NET SDK")
    if not _godotx.is_mono(_godotx.find_godot()):
        raise Skip("Godot build is not .NET")
    return exe


def gdunit_addon():
    """Path to a cached gdUnit4 addon folder (downloaded once); Skip when offline."""
    cache = _godotx.cache_dir() / f"gdUnit4-{GDUNIT_VERSION}"
    addon = cache / f"gdUnit4-{GDUNIT_VERSION}" / "addons" / "gdUnit4"
    if not addon.is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        z = cache / "src.zip"
        try:
            urllib.request.urlretrieve(f"https://github.com/godot-gdunit-labs/gdUnit4/archive/refs/tags/v{GDUNIT_VERSION}.zip", z)
        except OSError as e:
            raise Skip(f"cannot download gdUnit4: {e}")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(cache)
    return addon


def main():
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    if not _godotx.find_godot():
        print("Godot not found; set GODOT_EXE")
        return 2
    sys.path.insert(0, str(HERE))
    passed, failed, skipped = 0, [], 0
    for f in sorted(HERE.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            full = f"{f.stem}::{name}"
            if flt and flt not in full:
                continue
            t0 = time.time()
            try:
                getattr(mod, name)()
                passed += 1
                print(f"PASS {full} ({time.time() - t0:.1f}s)", flush=True)
            except Skip as e:
                skipped += 1
                print(f"SKIP {full}: {e}", flush=True)
            except Exception:
                failed.append(full)
                print(f"FAIL {full}\n{traceback.format_exc()}", flush=True)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"{passed} passed, {len(failed)} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
