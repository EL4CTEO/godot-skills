#!/usr/bin/env python3
"""Compile-check GDScript files with the real engine (parser + analyzer + compiler), one process.

Usage:
  python gd_check.py [PATHS...] [--project DIR] [--addons] [--no-import]
    PATHS: .gd files or folders (default: whole project, addons/ skipped unless --addons)
  Runs `--import` first when the class_name cache (.godot/) is missing or older than the scripts.
  Autoload names resolve like at runtime; autoload _ready() never runs (only _init()).
Output: {"ok", "checked", "errors": [{"file","line","msg"}], "seconds"}
"""
import os
import pathlib
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, godot_or_exit, parse_messages, project_or_exit, res_path, run, runner  # noqa: E402


def collect(root, paths, addons):
    out = []
    for p in paths or [str(root)]:
        p = pathlib.Path(p.replace("res://", str(root) + "/")) if p.startswith("res://") else pathlib.Path(p).resolve()
        if p.is_file() and p.suffix == ".gd":
            out.append(p)
        elif p.is_dir():
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if not d.startswith(".") and (addons or not (d == "addons" and pathlib.Path(dp) == root))]
                out += [pathlib.Path(dp) / f for f in fns if f.endswith(".gd")]
    return sorted(set(out))


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj, paths = None, []
    it = iter(argv)
    for a in it:
        if a == "--project":
            proj = next(it)
        elif not a.startswith("--"):
            paths.append(a)
    root = project_or_exit(proj or (paths[0] if paths and not paths[0].startswith("res://") else "."))
    exe = godot_or_exit()
    t0 = time.time()
    files = collect(root, paths, "--addons" in argv)
    cache = root / ".godot" / "global_script_class_cache.cfg"
    newest = max((f.stat().st_mtime for f in files), default=0)
    if "--no-import" not in argv and (not cache.is_file() or cache.stat().st_mtime < newest):
        run(["--import"], project=root, timeout=600, exe=exe)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8", newline="\n") as f:
        f.write("\n".join(res_path(root, x) for x in files))
        lst = f.name
    try:
        r = run(["--script", runner(__file__, "gd_check.gd"), "--", lst], project=root, timeout=1800, exe=exe)
    finally:
        os.unlink(lst)
    errors, cur = [], None
    chunks = re.split(r"^@@(?:FILE|DONE) (\S+).*$", r["out"] + "\n" + r["err"], flags=re.M)
    # chunks: [pre, path1, text1, path1, text1b, path2, ...] -> attribute location-less errors to the current file
    for i in range(1, len(chunks) - 1, 2):
        cur, text = chunks[i], chunks[i + 1]
        for m in parse_messages(text):
            if "error" not in m["type"] or m["msg"].startswith("Failed to load script"):
                continue
            msg = re.sub(r"^(Parse|Compile) Error: ", "", m["msg"])
            errors.append({"file": m.get("file", cur), "line": m.get("line"), "msg": msg})
    for failed in re.findall(r"^@@DONE (\S+) false", r["out"], flags=re.M):
        if not any(e["file"] == failed for e in errors):
            errors.append({"file": failed, "line": None, "msg": "failed to load (dependency error or missing file)"})
    seen, uniq = set(), []
    for e in errors:
        k = (e["file"], e["line"], e["msg"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    res = {"ok": not uniq, "checked": len(files), "errors": uniq[:100], "error_count": len(uniq),
           "seconds": round(time.time() - t0, 1)}
    if "@@DONE" not in r["out"] and files:
        res.update(ok=False, runner_failed=True, tail=(r["out"] + r["err"]).strip().splitlines()[-15:])
    emit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
