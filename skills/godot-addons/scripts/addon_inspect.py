#!/usr/bin/env python3
"""Inspect a project's addons: plugins, GDExtensions, versions, enabled state and compatibility problems.

Usage:
  python addon_inspect.py [DIR]                 report every addons/<name>/ folder (static, no engine)
  python addon_inspect.py [DIR] --enable NAME   add res://addons/NAME/plugin.cfg to [editor_plugins] enabled
  python addon_inspect.py [DIR] --disable NAME  remove it (close the editor first, or it may rewrite the file)
Checks: plugin.cfg fields and script, GDExtension compatibility_minimum/maximum vs the engine target,
native libraries missing for platforms in export_presets.cfg, C# addons in non-.NET projects,
Godot 3 syntax in addon scripts, enabled plugins whose folder is gone, addons made obsolete by the engine.
Output: {"ok", "engine_target", "addons": [{name, kind, version, enabled, warnings}], "warnings"}
"""
import configparser
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import TARGET, emit, project_or_exit  # noqa: E402

OBSOLETE = {
    "godot-jolt": "Jolt is built into Godot 4.4+ (default for new 4.6+ projects): remove the addon and set physics/3d/physics_engine",
    "godot_jolt": "Jolt is built into Godot 4.4+: remove the addon",
}
PRESET_FEATURE = {"Windows Desktop": "windows", "Linux": "linux", "Linux/X11": "linux", "macOS": "macos",
                  "Android": "android", "iOS": "ios", "Web": "web"}
G3 = re.compile(r"^(tool\s*$|export(\(.*\))?\s+var\b|onready\s+var\b)|\byield\s*\(", re.M)


def ini(path):
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    try:
        cp.read_string(path.read_text("utf-8", "replace"))
    except configparser.Error:
        return None
    return cp


def val(cp, sec, key, default=""):
    try:
        return cp.get(sec, key).strip().strip('"')
    except (configparser.Error, AttributeError):
        return default


def ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:2]) if s else ()


def enabled_list(text):
    m = re.search(r"^\[editor_plugins\]\s*\n(?:[^\[]*?\n)?enabled=PackedStringArray\(([^)]*)\)", text, re.M)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def export_features(root):
    f = root / "export_presets.cfg"
    if not f.is_file():
        return set()
    return {PRESET_FEATURE.get(p, p.lower()) for p in re.findall(r'^platform="([^"]+)"', f.read_text("utf-8", "replace"), re.M)}


def inspect(root):
    text = (root / "project.godot").read_text("utf-8", "replace")
    enabled = enabled_list(text)
    csharp = any(root.glob("*.csproj"))
    features = export_features(root)
    addons, warns = [], []
    adir = root / "addons"
    for d in sorted(p for p in adir.iterdir() if p.is_dir()) if adir.is_dir() else []:
        a = {"name": d.name, "kind": [], "version": "", "enabled": False, "warnings": []}
        files = [p for p in d.rglob("*") if p.is_file()]
        n_gd = sum(p.suffix == ".gd" for p in files)
        n_cs = sum(p.suffix == ".cs" for p in files)
        a["scripts"] = {"gd": n_gd, "cs": n_cs}
        cfgp = d / "plugin.cfg"
        if cfgp.is_file():
            a["kind"].append("editor_plugin")
            cp = ini(cfgp)
            a["version"] = val(cp, "plugin", "version")
            a["title"] = val(cp, "plugin", "name")
            script = val(cp, "plugin", "script")
            res = f"res://addons/{d.name}/plugin.cfg"
            a["enabled"] = res in enabled
            if script and not (d / script).is_file():
                a["warnings"].append(f"plugin.cfg script '{script}' not found")
            if not a["enabled"]:
                a["warnings"].append("not enabled (Project Settings > Plugins, or --enable)")
        for ext in d.rglob("*.gdextension"):
            a["kind"].append("gdextension")
            cp = ini(ext)
            lo, hi = val(cp, "configuration", "compatibility_minimum"), val(cp, "configuration", "compatibility_maximum")
            a.setdefault("gdextension", []).append({"file": "res://" + ext.relative_to(root).as_posix(), "min": lo, "max": hi})
            if lo and ver(lo) > TARGET:
                a["warnings"].append(f"{ext.name} needs Godot {lo}+")
            if hi and ver(hi) and ver(hi) < TARGET:
                a["warnings"].append(f"{ext.name} supports Godot up to {hi} only")
            libs = dict(cp.items("libraries")) if cp and cp.has_section("libraries") else {}
            plats = {k.split(".")[0] for k in libs}
            for feat in sorted(features - plats):
                a["warnings"].append(f"{ext.name} has no library for export platform '{feat}'")
            for k, v in libs.items():
                p = v.strip().strip('"')
                if p.startswith("res://") and not (root / p[6:]).exists():
                    a["warnings"].append(f"missing binary for {k}: {p}")
        if n_cs and not csharp:
            a["warnings"].append("contains C# scripts but the project has no .csproj (needs the .NET build)")
        if n_gd and any(G3.search(p.read_text("utf-8", "replace")) for p in files if p.suffix == ".gd"):
            a["warnings"].append("Godot 3 syntax in scripts: get the Godot 4 version of this addon")
        if d.name.lower() in OBSOLETE:
            a["warnings"].append(OBSOLETE[d.name.lower()])
        if not a["kind"]:
            a["kind"].append("library" if (n_gd or n_cs) else "assets")
        addons.append(a)
    for e in enabled:
        if not (root / e.replace("res://", "")).is_file():
            warns.append(f"enabled plugin missing on disk: {e}")
    return {"engine_target": "%d.%d" % TARGET, "csharp": csharp, "export_platforms": sorted(features),
            "addons": addons, "warnings": warns}


def set_enabled(root, name, on):
    pj = root / "project.godot"
    text = pj.read_text("utf-8")
    res = f"res://addons/{name}/plugin.cfg"
    if on and not (root / "addons" / name / "plugin.cfg").is_file():
        return {"ok": False, "error": f"{res} not found"}
    cur = enabled_list(text)
    new = sorted(set(cur) | {res}) if on else [e for e in cur if e != res]
    line = "enabled=PackedStringArray(" + ", ".join(f'"{e}"' for e in new) + ")"
    if re.search(r"^\[editor_plugins\]", text, re.M):
        if re.search(r"^enabled=PackedStringArray\([^)]*\)", text[text.index("[editor_plugins]"):], re.M):
            head, tail = text.split("[editor_plugins]", 1)
            tail = re.sub(r"^enabled=PackedStringArray\([^)]*\)", line, tail, count=1, flags=re.M)
            text = head + "[editor_plugins]" + tail
        else:
            text = text.replace("[editor_plugins]", "[editor_plugins]\n\n" + line, 1)
    elif on:
        text = text.rstrip("\n") + "\n\n[editor_plugins]\n\n" + line + "\n"
    pj.write_text(text, "utf-8", newline="\n")
    return {"ok": True, "enabled": new}


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    flags = {"--enable", "--disable"}
    name = next((argv[i + 1] for i, a in enumerate(argv) if a in flags and i + 1 < len(argv)), None)
    dirs = [a for a in argv if not a.startswith("--") and a != name]
    root = project_or_exit(dirs[0] if dirs else ".")
    if name:
        res = set_enabled(root, name, "--enable" in argv)
        emit(res)
        return 0 if res["ok"] else 1
    res = inspect(root)
    bad = res["warnings"] or any(w for a in res["addons"] for w in a["warnings"] if not w.startswith("not enabled"))
    res["ok"] = not bad
    emit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
