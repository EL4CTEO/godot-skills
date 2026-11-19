#!/usr/bin/env python3
"""Build a Godot C# project with the .NET SDK and get compact JSON errors.

Usage:
  python cs_build.py [--project DIR] [--config Debug|ExportDebug|ExportRelease] [--warnings]
  python cs_build.py --init [--project DIR]    create <Assembly>.csproj + .sln exactly like the
                                               Godot 4.7 editor (Sdk version = your engine version)
  python cs_build.py --doctor [--project DIR]  check dotnet SDK, csproj Sdk vs engine version, TFM
Build output lands in .godot/mono/temp/bin/<config>; the running editor/game picks it up.
Output: {"ok", "errors": [{"file","line","col","code","msg"}], "warning_count", "seconds"}
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, find_godot, project_or_exit, version  # noqa: E402

DIAG = re.compile(r"^(.*?)\((\d+),(\d+)\):\s+(error|warning)\s+(\w+):\s+(.*?)(?:\s+\[[^\]]*\])?$")


def dotnet():
    exe = shutil.which("dotnet")
    if not exe:
        for c in ("C:/Program Files/dotnet/dotnet.exe", "/usr/local/share/dotnet/dotnet", "/usr/share/dotnet/dotnet",
                  str(pathlib.Path.home() / ".dotnet/dotnet")):
            if os.path.isfile(c):
                return c
    return exe


def sdks(dn):
    out = subprocess.run([dn, "--list-sdks"], capture_output=True, text=True).stdout
    return [ln.split()[0] for ln in out.splitlines() if ln.strip()]


def engine_version():
    exe = find_godot()
    m = re.match(r"(\d+\.\d+(?:\.\d+)?)\.(\w+)", version(exe) if exe else "")
    if not m:
        return None
    v = m.group(1) if m.group(2) == "stable" else f"{m.group(1)}-{m.group(2)}"
    return v[:-2] if v.endswith(".0") and v.count(".") == 2 else v


def assembly_name(root):
    txt = (root / "project.godot").read_text("utf-8", errors="replace")
    m = re.search(r'^project/assembly_name="([^"]+)"', txt, re.M) or re.search(r'^config/name="([^"]+)"', txt, re.M)
    name = m.group(1) if m else root.name
    return re.sub(r"[^A-Za-z0-9_.]", "", name.replace(" ", "")) or "Game"


def init(root):
    ver = engine_version()
    if not ver:
        emit({"ok": False, "error": "need the Godot .NET executable to pick the Sdk version (set GODOT_EXE)"}, 2)
    name = assembly_name(root)
    csproj, sln = root / f"{name}.csproj", root / f"{name}.sln"
    if csproj.exists():
        emit({"ok": False, "error": f"{csproj.name} already exists"}, 1)
    csproj.write_text(
        f'<Project Sdk="Godot.NET.Sdk/{ver}">\n  <PropertyGroup>\n    <TargetFramework>net8.0</TargetFramework>\n'
        "    <TargetFramework Condition=\" '$(GodotTargetPlatform)' == 'android' \">net9.0</TargetFramework>\n"
        "    <EnableDynamicLoading>true</EnableDynamicLoading>\n  </PropertyGroup>\n</Project>", "utf-8")
    if not sln.exists():
        g = str(uuid.uuid4()).upper()
        cfgs = ("Debug", "ExportDebug", "ExportRelease")
        sln.write_text(
            "\ufeffMicrosoft Visual Studio Solution File, Format Version 12.00\n# Visual Studio 2012\n"
            f'Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "{name}", "{name}.csproj", "{{{g}}}"\nEndProject\n'
            "Global\n\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n"
            + "\n".join(f"\t{c}|Any CPU = {c}|Any CPU" for c in cfgs)
            + "\n\tEndGlobalSection\n\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n"
            + "\n".join(f"\t\t{{{g}}}.{c}|Any CPU.ActiveCfg = {c}|Any CPU\n\t\t{{{g}}}.{c}|Any CPU.Build.0 = {c}|Any CPU" for c in cfgs)
            + "\n\tEndGlobalSection\nEndGlobal\n", "utf-8")
    txt = (root / "project.godot").read_text("utf-8")
    if "[dotnet]" not in txt:
        (root / "project.godot").write_text(txt.rstrip("\n") + f'\n\n[dotnet]\n\nproject/assembly_name="{name}"\n', "utf-8")
    emit({"ok": True, "csproj": csproj.name, "sln": sln.name, "sdk": f"Godot.NET.Sdk/{ver}",
          "note": "add \"C#\" to config/features in project.godot if missing"})
    return 0


def doctor(root, dn):
    res = {"ok": True, "dotnet": dn, "sdks": sdks(dn) if dn else [], "engine": engine_version(), "issues": []}
    if not dn or not res["sdks"]:
        res["issues"].append("no .NET SDK: install .NET 8+ SDK (https://dotnet.microsoft.com/download)")
    elif max(int(s.split(".")[0]) for s in res["sdks"]) < 8:
        res["issues"].append("Godot 4.7 needs .NET SDK 8 or newer")
    projs = sorted(root.glob("*.csproj"))
    if not projs:
        res["issues"].append("no .csproj: run cs_build.py --init")
    else:
        txt = projs[0].read_text("utf-8", errors="replace")
        sdk = (re.search(r'Sdk="Godot\.NET\.Sdk/([^"]+)"', txt) or [None, None])[1]
        tfm = re.findall(r"<TargetFrameworks?[^>]*>([^<]+)<", txt)
        res.update({"csproj": projs[0].name, "sdk_version": sdk, "tfm": tfm})
        if sdk and res["engine"] and sdk != res["engine"]:
            res["issues"].append(f"csproj Godot.NET.Sdk/{sdk} != engine {res['engine']}: update the Sdk attribute")
        if tfm and not any(re.match(r"net(8|9|1\d)\.", t) for t in tfm):
            res["issues"].append(f"TargetFramework {tfm} too old: use net8.0+")
    res["ok"] = not res["issues"]
    emit(res)
    return 0 if res["ok"] else 1


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj = argv[argv.index("--project") + 1] if "--project" in argv else "."
    root = project_or_exit(proj)
    dn = dotnet()
    if "--init" in argv:
        return init(root)
    if "--doctor" in argv:
        return doctor(root, dn)
    if not dn:
        emit({"ok": False, "error": "dotnet not found: install the .NET 8+ SDK"}, 2)
    projs = sorted(root.glob("*.csproj"))
    if not projs:
        emit({"ok": False, "error": "no .csproj in project root (run --init)"}, 2)
    cfg = argv[argv.index("--config") + 1] if "--config" in argv else "Debug"
    t0 = time.time()
    p = subprocess.run([dn, "build", str(projs[0]), "-c", cfg, "-nologo", "-v", "q", "-clp:NoSummary",
                        "-p:GenerateFullPaths=true"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(root),
                       env={**os.environ, "DOTNET_CLI_UI_LANGUAGE": "en", "VSLANG": "1033", "DOTNET_NOLOGO": "1"})
    errs, warns, other = [], [], []
    for ln in (p.stdout + "\n" + p.stderr).splitlines():
        m = DIAG.match(ln.strip())
        if m:
            f = m.group(1)
            try:
                f = "res://" + pathlib.Path(f).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                pass
            d = {"file": f, "line": int(m.group(2)), "col": int(m.group(3)), "code": m.group(5), "msg": m.group(6)}
            (errs if m.group(4) == "error" else warns).append(d)
        elif "error" in ln.lower() and ln.strip():
            other.append(ln.strip()[:300])
    dedup = lambda xs: list({(x["file"], x["line"], x["code"], x["msg"]): x for x in xs}.values())  # noqa: E731
    errs, warns = dedup(errs), dedup(warns)
    res = {"ok": p.returncode == 0, "config": cfg, "errors": errs[:60], "error_count": len(errs),
           "warning_count": len(warns), "seconds": round(time.time() - t0, 1)}
    if "--warnings" in argv:
        res["warnings"] = warns[:60]
    if p.returncode and not errs:
        res["output"] = other[:20] or (p.stdout + p.stderr).strip().splitlines()[-20:]
    emit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
