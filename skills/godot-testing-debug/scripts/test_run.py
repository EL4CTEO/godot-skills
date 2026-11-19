#!/usr/bin/env python3
"""Run a Godot project's unit tests headless (GdUnit4 for GDScript, gdUnit4Net for C#) -> compact JSON.

Usage:
  python test_run.py [--project DIR] [--gd|--cs] [-a res://test/...]... [--filter EXPR]
    --gd     GDScript suites via addons/gdUnit4 (default when the addon exists); -a picks suites/dirs
             (default res://test and/or res://tests)
    --cs     C# tests via `dotnet test` (default when the .csproj references gdUnit4.api);
             --filter passes a dotnet test filter, e.g. "FullyQualifiedName~Player"
  Both run when both are set up and neither flag is given.
Output: {"ok", "gd": {"total","failed","failures": [{"test","file","line","msg"}]}, "cs": {...}}
"""
import glob
import os
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, godot_or_exit, project_or_exit, run  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_gd(root, adds):
    exe = godot_or_exit()
    if not (root / ".godot" / "global_script_class_cache.cfg").is_file():
        run(["--import"], project=root, timeout=600, exe=exe)
    adds = adds or [f"res://{d}" for d in ("test", "tests") if (root / d).is_dir()]
    if not adds:
        return {"ok": False, "error": "no test dir: put suites in res://test or pass -a"}
    rep = root / ".godot" / "gdunit_reports"
    # same flags as gdUnit4's runtest.sh: debug build behavior, but errors go to a dead remote
    # debugger instead of the interactive "debug>" stdin prompt (which would hang forever)
    args = ["-s", "-d", "--remote-debug", "tcp://127.0.0.1:0", "res://addons/gdUnit4/bin/GdUnitCmdTool.gd",
            "--ignoreHeadlessMode", "-c",
            "-rd", "res://.godot/gdunit_reports", "-rc", "1"]
    for a in adds:
        args += ["-a", a]
    r = run(args, project=root, timeout=1800, exe=exe)
    xmls = sorted(glob.glob(str(rep / "report_*" / "results.xml")), key=os.path.getmtime)
    out = ANSI.sub("", r["out"])
    if not xmls:
        return {"ok": False, "rc": r["rc"], "error": "no report produced", "tail": out.strip().splitlines()[-25:]}
    tree = ET.parse(xmls[-1]).getroot()
    fails = []
    for tc in tree.iter("testcase"):
        for f in list(tc.iter("failure")) + list(tc.iter("error")):
            text = (f.text or "").strip()
            loc = re.search(r"(res://[^\s:]+):(\d+)", f.get("message", "") + text)
            fails.append({"test": f"{tc.get('classname')}.{tc.get('name')}", "file": loc.group(1) if loc else None,
                          "line": int(loc.group(2)) if loc else None,
                          "msg": re.sub(r"\s+", " ", re.sub(r"\tat '.*", "", text))[:400]})
    total = int(tree.get("tests", 0))
    return {"ok": r["rc"] == 0 and not fails, "total": total, "failed": len(fails), "failures": fails[:50],
            "orphans_or_errors": [ln.strip() for ln in out.splitlines() if "orphan" in ln.lower() and "| 0 orphans" not in ln][:5]}


def run_cs(root, flt):
    import shutil
    dn = shutil.which("dotnet") or ("C:/Program Files/dotnet/dotnet.exe" if os.path.isfile("C:/Program Files/dotnet/dotnet.exe") else None)
    if not dn:
        return {"ok": False, "error": "dotnet SDK not found"}
    env = {**os.environ, "GODOT_BIN": godot_or_exit(), "DOTNET_CLI_UI_LANGUAGE": "en", "DOTNET_NOLOGO": "1"}
    cmd = [dn, "test", "--logger", "console;verbosity=normal"]
    if (root / ".runsettings").is_file():
        cmd += ["--settings", ".runsettings"]
    if flt:
        cmd += ["--filter", flt]
    p = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    out = p.stdout + p.stderr
    fails, cur = [], None
    for ln in out.splitlines():
        m = re.match(r"^\s+Failed (\S+) \[", ln)
        if m:
            cur = {"test": m.group(1), "msg": ""}
            fails.append(cur)
            continue
        if cur is not None:
            loc = re.search(r" in (.+?):line (\d+)", ln)
            if loc and "file" not in cur:
                cur["file"], cur["line"] = loc.group(1), int(loc.group(2))
                try:
                    cur["file"] = "res://" + pathlib.Path(cur["file"]).resolve().relative_to(root.resolve()).as_posix()
                except ValueError:
                    pass
                cur = None  # message and location captured
            elif ln.strip() and not ln.strip().startswith(("Error Message", "Stack Trace", "at ")) and len(cur["msg"]) < 300:
                cur["msg"] = (cur["msg"] + " " + ln.strip()).strip()
    summ = re.search(r"Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+(\d+), Total:\s+(\d+)", out) or \
        re.search(r"Passed!\s+-\s+Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+(\d+), Total:\s+(\d+)", out)
    res = {"ok": p.returncode == 0, "failures": fails[:50]}
    if summ:
        res.update({"failed": int(summ.group(1)), "passed": int(summ.group(2)), "skipped": int(summ.group(3)),
                    "total": int(summ.group(4))})
    else:  # verbose logger format: "Total tests: 3 / Passed: 2 / Failed: 1"
        nums = {k.lower(): int(v) for k, v in re.findall(r"^\s*(Total tests|Passed|Failed|Skipped):\s+(\d+)\s*$", out, re.M)}
        if nums:
            summ = True
            res.update({"total": nums.get("total tests", 0), "passed": nums.get("passed", 0),
                        "failed": nums.get("failed", 0), "skipped": nums.get("skipped", 0)})
    build_errs = sorted(set(re.findall(r"\): error (\w+: .*?)(?: \[|$)", out, re.M)))
    if build_errs:
        res["build_errors"] = build_errs[:20]
    if "Connection timeout" in out or "GodotRuntimeExecutor failed" in out:
        res["hint"] = "Godot runtime tests timed out: add .runsettings with <GdUnit4><Parameters>--headless</Parameters><GodotConnectTimeout>60000</GodotConnectTimeout></GdUnit4>"
    if not summ and not build_errs:
        res["tail"] = out.strip().splitlines()[-25:]
    return res


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj, adds, flt = ".", [], None
    it = iter(argv)
    for a in it:
        if a == "--project":
            proj = next(it)
        elif a == "-a":
            adds.append(next(it))
        elif a == "--filter":
            flt = next(it)
    root = project_or_exit(proj)
    has_gd = (root / "addons" / "gdUnit4" / "bin" / "GdUnitCmdTool.gd").is_file()
    has_cs = any("gdUnit4.api" in p.read_text("utf-8", errors="replace") for p in root.glob("*.csproj"))
    want_gd = "--gd" in argv or ("--cs" not in argv and has_gd)
    want_cs = "--cs" in argv or ("--gd" not in argv and has_cs)
    if not (want_gd or want_cs):
        emit({"ok": False, "error": "no test framework found",
              "hint": "GDScript: copy addons/gdUnit4 (github.com/godot-gdunit-labs/gdUnit4). C#: add gdUnit4.api, "
                      "gdUnit4.test.adapter, gdUnit4.analyzers + Microsoft.NET.Test.Sdk to the .csproj"}, 2)
    res = {}
    if want_gd:
        res["gd"] = run_gd(root, adds) if has_gd else {"ok": False, "error": "addons/gdUnit4 missing"}
    if want_cs:
        res["cs"] = run_cs(root, flt)
    res = {"ok": all(v.get("ok") for v in res.values()), **res}
    emit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
