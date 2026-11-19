#!/usr/bin/env python3
"""Validate Godot shaders (.gdshader) with the engine's own shader compiler, headless.

Usage:
  python shader_check.py [PATHS...] [--project DIR]
    PATHS: .gdshader files or folders (default: whole project, addons/ skipped)
  .gdshaderinc files are checked through the shaders that include them.
Output: {"ok", "checked", "errors": [{"file","line","msg"}]}
"""
import os
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, godot_or_exit, project_or_exit, res_path, run, runner  # noqa: E402

ERR = re.compile(r"^SHADER ERROR: (.*)$")
AT = re.compile(r"^\s+at: .*\(([^()]*):(\d+)\)\s*$")  # "at: (null) (:4)" / "(res://x.gdshaderinc:1)"


def collect(root, paths):
    out = []
    for p in paths or [str(root)]:
        p = pathlib.Path(p.replace("res://", str(root) + "/")) if p.startswith("res://") else pathlib.Path(p).resolve()
        if p.is_file() and p.suffix == ".gdshader":
            out.append(p)
        elif p.is_dir():
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if not d.startswith(".") and not (d == "addons" and pathlib.Path(dp) == root)]
                out += [pathlib.Path(dp) / f for f in fns if f.endswith(".gdshader")]
    return sorted(set(out))


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj = argv[argv.index("--project") + 1] if "--project" in argv else None
    paths = [a for a in argv if not a.startswith("--") and a != proj]
    root = project_or_exit(proj or ".")
    exe = godot_or_exit()
    files = collect(root, paths)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8", newline="\n") as f:
        f.write("\n".join(res_path(root, x) for x in files))
        lst = f.name
    try:
        r = run(["--script", runner(__file__, "shader_check.gd"), "--", lst], project=root, timeout=900, exe=exe)
    finally:
        os.unlink(lst)
    errors, cur, pending = [], None, None
    for line in r["err"].splitlines():
        if line.startswith("@@SHADER "):
            cur = line[len("@@SHADER "):].strip()
            continue
        m = ERR.match(line)
        if m:
            pending = {"file": cur, "line": None, "msg": m.group(1).strip()}
            errors.append(pending)
            continue
        a = AT.match(line)
        if a and pending is not None:
            if a.group(1) not in ("", "(null)"):  # error inside an included .gdshaderinc
                pending["file"] = a.group(1)
            pending["line"] = int(a.group(2))
            pending = None
    uniq = list({(e["file"], e["line"], e["msg"]): e for e in errors}.values())
    res = {"ok": not uniq and "@@END" in r["err"], "checked": len(files), "errors": uniq[:100]}
    if "@@END" not in r["err"]:
        res["tail"] = (r["out"] + r["err"]).strip().splitlines()[-15:]
    emit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
