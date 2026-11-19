#!/usr/bin/env python3
"""List export presets, check templates, export headless and verify the artifact.

Usage:
  python export.py --list [--project DIR]                  presets (name, platform, path) + template status
  python export.py "Windows Desktop" [--debug|--pack|--patch] [--out PATH] [--project DIR] [--timeout S]
      default mode is --export-release. --out overrides the preset's export_path.
      C# projects are built by the export itself (needs the .NET SDK).
Output: {"ok", "preset", "out", "bytes", "errors": [...], "seconds"}
"""
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, godot_or_exit, parse_messages, project_or_exit, run, version  # noqa: E402


def presets(root):
    f = root / "export_presets.cfg"
    if not f.is_file():
        return []
    out, cur = [], None
    for line in f.read_text("utf-8", errors="replace").splitlines():
        if re.match(r"^\[preset\.\d+\]$", line):
            cur = {}
            out.append(cur)
        elif line.startswith("[preset.") and line.endswith(".options]"):
            cur = None
        elif cur is not None and "=" in line:
            k, v = line.split("=", 1)
            if k in ("name", "platform", "export_path", "runnable", "export_filter"):
                cur[k] = v.strip().strip('"')
    return out


def templates_dir(exe):
    m = re.match(r"(\d+\.\d+(?:\.\d+)?)\.(\w+)", version(exe))
    if not m:
        return None
    tag = f"{m.group(1)}.{m.group(2)}" + (".mono" if "mono" in version(exe) else "")
    home = pathlib.Path.home()
    if os.name == "nt":
        base = pathlib.Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / "Godot"
    elif sys.platform == "darwin":
        base = home / "Library/Application Support/Godot"
    else:
        base = pathlib.Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "godot"
    exe_dir = pathlib.Path(exe).parent
    if (exe_dir / "._sc_").exists() or (exe_dir / "_sc_").exists():  # self-contained mode
        base = exe_dir / "editor_data"
    return base / "export_templates" / tag


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj = argv[argv.index("--project") + 1] if "--project" in argv else "."
    root = project_or_exit(proj)
    exe = godot_or_exit()
    tdir = templates_dir(exe)
    tinfo = {"dir": str(tdir), "installed": bool(tdir and tdir.is_dir() and any(tdir.iterdir()))}
    ps = presets(root)
    if argv[0] == "--list":
        emit({"ok": True, "presets": ps, "templates": tinfo,
              "hint": None if ps else "no export_presets.cfg: add presets in the editor (Project > Export) or write one"})
        return 0
    name = argv[0]
    pre = next((p for p in ps if p.get("name") == name), None)
    if not pre:
        emit({"ok": False, "error": f"preset {name!r} not found", "presets": [p.get("name") for p in ps]}, 1)
    mode = "--export-debug" if "--debug" in argv else "--export-pack" if "--pack" in argv else \
        "--export-patch" if "--patch" in argv else "--export-release"
    out = argv[argv.index("--out") + 1] if "--out" in argv else pre.get("export_path", "")
    if not out:
        emit({"ok": False, "error": "preset has no export_path; pass --out"}, 1)
    out_abs = pathlib.Path(out) if os.path.isabs(out) else (root / out)
    out_abs.parent.mkdir(parents=True, exist_ok=True)
    timeout = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 1800
    t0 = time.time()
    r = run([mode, name, str(out_abs)], project=root, timeout=timeout, exe=exe)
    msgs = [m for m in parse_messages(r["out"] + "\n" + r["err"], keep_engine=True) if "error" in m["type"]]
    ok = r["rc"] == 0 and out_abs.exists() and out_abs.stat().st_size > 0
    res = {"ok": ok, "preset": name, "platform": pre.get("platform"), "mode": mode[2:], "out": str(out_abs),
           "bytes": out_abs.stat().st_size if out_abs.exists() else 0, "errors": msgs[:30], "seconds": round(time.time() - t0, 1)}
    if not ok and not tinfo["installed"] and mode != "--export-pack":
        res["hint"] = f"export templates missing in {tdir}: Editor > Manage Export Templates > Download (4.7 can fetch per platform)"
    emit(res)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
