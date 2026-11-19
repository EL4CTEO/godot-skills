#!/usr/bin/env python3
"""Run Godot headless and get compact JSON (errors parsed, output tail).

Usage:
  python run_godot.py version                          engine path + version (+ .NET or not)
  python run_godot.py import [--project DIR]           import assets, build class_name cache (.godot/)
  python run_godot.py smoke [SCENE] [--frames 120]     run main scene (or SCENE) headless N frames, report errors
  python run_godot.py script FILE.gd [--project DIR] [-- user args]   run an `extends SceneTree` script
  python run_godot.py raw [--project DIR] -- <godot args>             anything else
  common: --project DIR (default: nearest project.godot above cwd)  --timeout S (default 300)
          --tail N (stdout lines kept, default 30)
Exit code = Godot's exit code. GODOT_EXE overrides engine discovery.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, find_project, godot_or_exit, is_mono, parse_messages, project_or_exit, run, version  # noqa: E402


def opts(argv):
    o = {"project": None, "timeout": 300, "tail": 30, "frames": 120, "pos": [], "rest": []}
    if "--" in argv:
        i = argv.index("--")
        argv, o["rest"] = argv[:i], argv[i + 1:]
    it = iter(argv)
    for a in it:
        if a in ("--project", "--timeout", "--tail", "--frames"):
            v = next(it)
            o[a[2:]] = v if a == "--project" else int(v)
        else:
            o["pos"].append(a)
    return o


def report(r, tail, extra=None):
    text = r["out"] + "\n" + r["err"]
    msgs = parse_messages(text)
    lines = [ln for ln in r["out"].splitlines() if ln.strip() and not ln.startswith("Godot Engine v")
             and "GDScript backtrace" not in ln and not ln.startswith("       [")]
    res = {"ok": r["rc"] == 0 and not any(m["type"] in ("error", "script_error") for m in msgs), "rc": r["rc"],
           "errors": [m for m in msgs if "error" in m["type"]][:40],
           "warnings": [m for m in msgs if "warning" in m["type"]][:20], "stdout_tail": lines[-tail:]}
    if r["err"].startswith("timeout"):
        res["timeout"] = True
    res.update(extra or {})
    return res


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, o = argv[0], opts(argv[1:])
    if cmd == "version":
        exe = godot_or_exit()
        emit({"ok": True, "exe": exe, "version": version(exe), "dotnet": is_mono(exe)})
        return 0
    proj = o["project"] or (find_project() if cmd == "raw" else project_or_exit())
    if cmd == "import":
        r = run(["--import"], project=proj, timeout=o["timeout"])
        res = report(r, 5)
        res["class_cache"] = os.path.isfile(os.path.join(proj, ".godot", "global_script_class_cache.cfg"))
    elif cmd == "smoke":
        args = ["--quit-after", str(o["frames"])] + o["pos"][:1]
        res = report(run(args, project=proj, timeout=o["timeout"]), o["tail"], {"frames": o["frames"]})
    elif cmd == "script":
        if not o["pos"]:
            emit({"ok": False, "error": "script needs FILE.gd"}, 2)
        path = o["pos"][0]
        if not path.startswith("res://"):
            path = os.path.abspath(path)
        args = ["--script", path] + (["--"] + o["rest"] if o["rest"] else [])
        res = report(run(args, project=proj, timeout=o["timeout"]), o["tail"])
    elif cmd == "raw":
        res = report(run(o["rest"], project=proj, timeout=o["timeout"]), o["tail"])
    else:
        emit({"ok": False, "error": f"unknown command {cmd}"}, 2)
    emit(res)
    return res.get("rc", 0) if res.get("rc", 0) >= 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
