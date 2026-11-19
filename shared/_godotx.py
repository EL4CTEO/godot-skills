"""Shared helpers for godot-agent-skills scripts (stdlib only, Python 3.9+).

Edit shared/_godotx.py only; tools/sync_shared.py copies it into skills/*/scripts/.
Finds the Godot executable, runs it headless, parses its error output, prints compact JSON.
"""
import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

TARGET = (4, 7)  # skills are written for Godot 4.7.x
ERR_RE = re.compile(r"^(SCRIPT ERROR|ERROR|WARNING|USER ERROR|USER WARNING|SCRIPT WARNING):\s*(.*)$")
AT_RE = re.compile(r"^\s+at:\s*(.*?)\s*\((.*?):(\d+)\)\s*$")


def emit(obj, code=None):
    """Print one compact JSON object and optionally exit."""
    print(json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=str))
    if code is not None:
        sys.exit(code)


def _candidates():
    for k in ("GODOT_EXE", "GODOT", "GODOT_BIN"):
        if os.environ.get(k):
            yield os.environ[k]
    for n in ("godot-mono", "godot4-mono", "godot", "godot4"):
        p = shutil.which(n)
        if p:
            yield p
    home = pathlib.Path.home()
    pats = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", str(home / "AppData/Local"))
        for base in (f"{la}/Programs/Godot", f"{la}/Godot", "C:/Program Files/Godot", "C:/Godot",
                     str(home / "Godot"), str(home / "Downloads"), str(home / "Desktop"),
                     "C:/Program Files (x86)/Steam/steamapps/common/Godot Engine"):
            # shallow patterns only: recursive globs over Desktop/Downloads can take minutes
            pats += [f"{base}/Godot_v4*.exe", f"{base}/*/Godot_v4*.exe", f"{base}/*/*/Godot_v4*.exe"]
    elif sys.platform == "darwin":
        pats += ["/Applications/Godot*.app/Contents/MacOS/Godot",
                 str(home / "Applications/Godot*.app/Contents/MacOS/Godot")]
    else:
        pats += [str(home / ".local/bin/Godot_v4*"), str(home / "bin/Godot_v4*"), "/opt/godot*/Godot_v4*",
                 str(home / ".local/share/godot/*/Godot_v4*")]
    found = []
    for pat in pats:
        found += glob.glob(pat)
    # newest version first, mono and console builds preferred
    def key(p):
        v = re.findall(r"v(\d+)\.(\d+)(?:\.(\d+))?", p)
        ver = tuple(int(x or 0) for x in v[-1]) if v else (0, 0, 0)
        return (ver, "mono" in p.lower(), "console" in p.lower())
    for p in sorted(found, key=key, reverse=True):
        if "template" not in p.lower():
            yield p


def find_godot():
    """Return the path of a Godot 4 executable, or None. GODOT_EXE overrides discovery."""
    for p in _candidates():
        if p and os.path.isfile(p):
            p = os.path.normpath(p)
            if os.name == "nt" and not p.lower().endswith("_console.exe"):
                con = p[:-4] + "_console.exe"
                if os.path.isfile(con):
                    return con  # console build: stdout is captured reliably
            return p
    return None


def godot_or_exit():
    exe = find_godot()
    if not exe:
        emit({"ok": False, "error": "Godot not found; set GODOT_EXE to the Godot 4.7 (.NET) executable"}, 2)
    return exe


def version(exe):
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60,
                         encoding="utf-8", errors="replace").stdout.strip().splitlines()
    return out[-1] if out else ""


def is_mono(exe):
    return "mono" in version(exe) or "mono" in os.path.basename(exe).lower()


def find_project(start="."):
    """Walk up from start to the folder holding project.godot."""
    p = pathlib.Path(start).resolve()
    if p.is_file():
        p = p.parent
    for d in (p, *p.parents):
        if (d / "project.godot").is_file():
            return d
    return None


def project_or_exit(start="."):
    d = find_project(start)
    if not d:
        emit({"ok": False, "error": f"no project.godot at or above {start}"}, 2)
    return d


def run(args, project=None, timeout=600, headless=True, exe=None):
    """Run Godot. Returns dict(rc, out, err). Adds --headless and --path <project>."""
    exe = exe or godot_or_exit()
    cmd = [exe] + (["--headless"] if headless else []) + (["--path", str(project)] if project else []) + list(args)
    try:
        # stdin=DEVNULL: a "-d" debugger prompt or any read can never block an agent's run
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL)
        return {"rc": p.returncode, "out": p.stdout, "err": p.stderr, "cmd": cmd}
    except subprocess.TimeoutExpired as e:
        return {"rc": -1, "out": (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                "err": f"timeout after {timeout}s", "cmd": cmd}


def parse_messages(text, keep_engine=False):
    """Parse Godot's 'ERROR: msg' + '   at: func (file:line)' pairs into dicts.

    keep_engine=False drops errors located in engine C++ sources (only res:// and user files kept)
    unless no file is known at all.
    """
    msgs, cur = [], None
    for line in text.splitlines():
        m = ERR_RE.match(line)
        if m:
            cur = {"type": m.group(1).lower().replace(" ", "_"), "msg": m.group(2).strip()}
            msgs.append(cur)
            continue
        a = AT_RE.match(line)
        if a and cur is not None and "file" not in cur:
            cur["file"], cur["line"] = a.group(2), int(a.group(3))
            cur = None
        elif cur is not None and line.strip() and not line.startswith(("[", " ")) and len(cur["msg"]) < 600:
            cur["msg"] += " | " + line.strip()  # multi-line message (e.g. export configuration errors)
    if not keep_engine:
        msgs = [m for m in msgs if "file" not in m or m["file"].startswith(("res://", "user://"))
                or m["file"].endswith((".gd", ".cs", ".tscn", ".tres"))]
    seen, out = set(), []
    for m in msgs:  # Godot often repeats a parse error twice with different wording
        k = (m.get("file"), m.get("line"), m["type"])
        if k in seen and m["type"] == "script_error":
            continue
        seen.add(k)
        out.append(m)
    return out


def cache_dir():
    base = os.environ.get("GODOT_SKILLS_CACHE")
    if not base:
        if os.name == "nt":
            base = os.path.join(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home())), "godot-agent-skills")
        else:
            base = os.path.join(os.environ.get("XDG_CACHE_HOME", str(pathlib.Path.home() / ".cache")), "godot-agent-skills")
    os.makedirs(base, exist_ok=True)
    return pathlib.Path(base)


def res_path(project, path):
    """Absolute/relative file path -> res:// path (unchanged if already res://)."""
    if str(path).startswith("res://"):
        return str(path)
    rel = pathlib.Path(path).resolve().relative_to(pathlib.Path(project).resolve())
    return "res://" + rel.as_posix()


def runner(script_file, name):
    """Absolute path of a GDScript helper shipped next to script_file (pass __file__)."""
    return str(pathlib.Path(script_file).resolve().parent / name)
