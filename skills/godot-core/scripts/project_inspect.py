#!/usr/bin/env python3
"""Summarize a Godot project or scene WITHOUT opening Godot (pure text parsing, fast, token-lean).

Usage:
  python project_inspect.py [DIR]                    project summary: renderer, physics, autoloads,
                                                     input map, stretch, layers, C# setup, file counts
  python project_inspect.py --scene res://x.tscn     node tree: name (Type) script/instance, signals
       [--props]                                     ...plus each node's non-default properties
  python project_inspect.py --setting KEY [DIR]      raw value of one project.godot setting
  python project_inspect.py --files [DIR] [--ext gd,cs,tscn]   list project files (skips .godot, addons)
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, project_or_exit  # noqa: E402

KEYS = {32: "Space", 4194305: "Escape", 4194306: "Tab", 4194308: "Backspace", 4194309: "Enter",
        4194310: "KpEnter", 4194312: "Delete", 4194319: "Left", 4194320: "Up", 4194321: "Right",
        4194322: "Down", 4194325: "Shift", 4194326: "Ctrl", 4194328: "Alt", 4194329: "Meta"}
JOY_BTN = ["A", "B", "X", "Y", "Back", "Guide", "Start", "LStick", "RStick", "LB", "RB",
           "DUp", "DDown", "DLeft", "DRight", "Misc1", "Paddle1", "Paddle2", "Paddle3", "Paddle4", "Touchpad"]
JOY_AXIS = ["LX", "LY", "RX", "RY", "LT", "RT"]
MOUSE = {1: "MouseLeft", 2: "MouseRight", 3: "MouseMiddle", 4: "WheelUp", 5: "WheelDown"}


def read_cfg(path):
    """Godot ConfigFile text -> {section: {key: raw_value_str}} (multi-line values joined)."""
    data, sec, key, buf, depth, in_str = {}, "", None, [], 0, False
    for line in pathlib.Path(path).read_text("utf-8", errors="replace").splitlines():
        if key is None:
            s = line.strip()
            if not s or s.startswith(";"):
                continue
            m = re.match(r"^\[(.+)\]$", s)
            if m:
                sec = m.group(1)
                data.setdefault(sec, {})
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, buf = key.strip(), [val]
        else:
            buf.append(line)
        txt = "\n".join(buf)
        depth, in_str, esc = 0, False, False
        for ch in txt:
            if in_str:
                esc = (ch == "\\" and not esc)
                if ch == '"' and not esc:
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[(":
                depth += 1
            elif ch in "}])":
                depth -= 1
        if depth <= 0 and not in_str:
            data.setdefault(sec, {})[key] = txt.strip()
            key = None
    return data


def unq(v):
    v = (v or "").strip()
    return v[1:-1] if len(v) >= 2 and v[0] == '"' and v[-1] == '"' else v


def summarize_event(obj):
    t = re.match(r"Object\((\w+)", obj).group(1)
    g = lambda k: (re.search(rf'"{k}":(-?[\d.]+)', obj) or [None, None])[1]  # noqa: E731
    mods = [m for m in ("ctrl", "shift", "alt", "meta") if f'"{m}_pressed":true' in obj]
    if t == "InputEventKey":
        code = int(g("physical_keycode") or 0) or int(g("keycode") or 0) or int(g("key_label") or 0)
        name = KEYS.get(code) or (chr(code) if 33 <= code < 127 else f"key{code}")
        return "+".join([*[m.title() for m in mods], name])
    if t == "InputEventMouseButton":
        return MOUSE.get(int(g("button_index") or 0), f"Mouse{g('button_index')}")
    if t == "InputEventJoypadButton":
        i = int(g("button_index") or 0)
        return "Joy" + (JOY_BTN[i] if 0 <= i < len(JOY_BTN) else str(i))
    if t == "InputEventJoypadMotion":
        i, v = int(g("axis") or 0), float(g("axis_value") or 0)
        return "Joy" + (JOY_AXIS[i] if 0 <= i < len(JOY_AXIS) else f"Axis{i}") + ("+" if v > 0 else "-")
    return t.replace("InputEvent", "")


def project_summary(root):
    cfg = read_cfg(root / "project.godot")
    app, ren, phy, disp = (cfg.get(s, {}) for s in ("application", "rendering", "physics", "display"))
    feats = re.findall(r'"([^"]+)"', app.get("config/features", ""))
    res = {"ok": True, "path": str(root), "name": unq(app.get("config/name")), "features": feats,
           "main_scene": unq(app.get("run/main_scene")) or None,
           "renderer": unq(ren.get("renderer/rendering_method")) or "forward_plus",
           "renderer_mobile": unq(ren.get("renderer/rendering_method.mobile")) or None,
           "physics_3d": unq(phy.get("3d/physics_engine")) or "DEFAULT (GodotPhysics3D; 4.6+ new projects store Jolt Physics)",
           "physics_2d": unq(phy.get("2d/physics_engine")) or "DEFAULT",
           "physics_tick": phy.get("common/physics_ticks_per_second", "60"),
           "physics_interpolation": phy.get("common/physics_interpolation", "false"),
           "stretch": {k.split("/")[-1]: unq(v) for k, v in disp.items() if k.startswith("window/stretch/")},
           "window": {k.split("/")[-1]: unq(v) for k, v in disp.items() if k.startswith("window/size/")}}
    res["autoloads"] = {k: unq(v).lstrip("*") for k, v in cfg.get("autoload", {}).items()}
    inp = {}
    for act, raw in cfg.get("input", {}).items():
        inp[act] = [summarize_event(o) for o in re.findall(r"Object\([^)]*\)", raw)]
    res["input"] = inp
    layers = cfg.get("layer_names", {})
    res["layer_names"] = {k: unq(v) for k, v in layers.items()}
    plugins = cfg.get("editor_plugins", {}).get("enabled", "")
    res["plugins"] = re.findall(r'"res://addons/([^/"]+)', plugins)
    res["globals"] = {k: unq(v) for k, v in cfg.get("global_group", {}).items()} or None
    dn = cfg.get("dotnet", {})
    csproj = sorted(root.glob("*.csproj"))
    if csproj or dn:
        txt = csproj[0].read_text("utf-8", errors="replace") if csproj else ""
        res["csharp"] = {"csproj": csproj[0].name if csproj else None,
                         "sdk": (re.search(r'Sdk="([^"]+)"', txt) or [None, None])[1],
                         "tfm": (re.search(r"<TargetFrameworks?>([^<]+)<", txt) or [None, None])[1],
                         "assembly": unq(dn.get("project/assembly_name")) or None}
    counts = {}
    for p in iter_files(root):
        counts[p.suffix[1:]] = counts.get(p.suffix[1:], 0) + 1
    res["files"] = {k: counts[k] for k in ("gd", "cs", "tscn", "tres", "gdshader", "glb", "gltf", "blend", "fbx", "png", "wav", "ogg")
                    if k in counts}
    res["addons"] = sorted(p.name for p in (root / "addons").iterdir() if p.is_dir()) if (root / "addons").is_dir() else []
    res["imported"] = (root / ".godot" / "global_script_class_cache.cfg").is_file()
    cache = root / ".godot" / "global_script_class_cache.cfg"
    if cache.is_file():
        res["class_names"] = sorted(set(re.findall(r'"class": &"(\w+)"', cache.read_text("utf-8", errors="replace"))))[:200]
    return {k: v for k, v in res.items() if v not in (None, {}, [], "")}


def iter_files(root, exts=None, skip_addons=True):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".") and d not in ("bin", "obj")
                  and not (skip_addons and d == "addons" and pathlib.Path(dp) == root)]
        for f in fns:
            p = pathlib.Path(dp) / f
            if exts is None or p.suffix[1:] in exts:
                yield p


def scene_tree(root, scene, props):
    path = root / scene.replace("res://", "") if scene.startswith("res://") else pathlib.Path(scene)
    text = path.read_text("utf-8", errors="replace")
    ext, sub, nodes, conns, cur = {}, {}, [], [], None
    for line in text.splitlines():
        m = re.match(r"^\[(\w+)(.*)\]$", line)
        if m:
            kind, attrs = m.group(1), dict(re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|\w+\("[^"]*"\)|[^\s\]]+)', m.group(2)))
            cur = None
            if kind == "ext_resource":
                ext[unq(attrs.get("id"))] = unq(attrs.get("path"))
            elif kind == "sub_resource":
                sub[unq(attrs.get("id"))] = unq(attrs.get("type"))
            elif kind == "node":
                cur = {"name": unq(attrs.get("name")), "type": unq(attrs.get("type")), "parent": unq(attrs.get("parent")) if "parent" in attrs else None,
                       "props": {}}
                inst = re.search(r'ExtResource\("([^"]+)"\)', attrs.get("instance", ""))
                if inst:
                    cur["instance"] = ext.get(inst.group(1))
                nodes.append(cur)
            elif kind == "connection":
                conns.append(f'{unq(attrs.get("from"))}.{unq(attrs.get("signal"))} -> {unq(attrs.get("to"))}:{unq(attrs.get("method"))}')
            continue
        if cur is not None and " = " in line:
            k, v = line.split(" = ", 1)
            v = re.sub(r'ExtResource\("([^"]+)"\)', lambda mm: ext.get(mm.group(1), mm.group(0)), v)
            v = re.sub(r'SubResource\("([^"]+)"\)', lambda mm: f"<{sub.get(mm.group(1), '?')}>", v)
            cur["props"][k.strip()] = v.strip()[:120]
    lines = []
    for n in nodes:
        par = n["parent"]
        depth = 0 if par is None else (1 if par == "." else par.count("/") + 2)
        desc = n["name"] + (f" ({n['type']})" if n["type"] else "")
        if n.get("instance"):
            desc += f" [inst {n['instance']}]"
        if "script" in n["props"]:
            desc += f" script={n['props']['script']}"
        if props:
            extra = {k: v for k, v in n["props"].items() if k != "script"}
            if extra:
                desc += " " + " ".join(f"{k}={v}" for k, v in extra.items())
        lines.append("  " * depth + desc)
    return {"ok": True, "scene": scene, "nodes": len(nodes), "tree": lines, "connections": conns,
            "sub_resources": sorted(set(sub.values()))}


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if "--scene" in argv:
        i = argv.index("--scene")
        scene = argv[i + 1]
        rest = [a for a in argv if a not in ("--scene", scene, "--props")]
        root = project_or_exit(rest[0] if rest else (scene if not scene.startswith("res://") else "."))
        emit(scene_tree(root, scene, "--props" in argv))
        return 0
    if "--setting" in argv:
        i = argv.index("--setting")
        key = argv[i + 1]
        rest = [a for a in argv if a not in ("--setting", key)]
        root = project_or_exit(rest[0] if rest else ".")
        sec, _, k = key.partition("/")
        val = read_cfg(root / "project.godot").get(sec, {}).get(k)
        emit({"ok": val is not None, "key": key, "value": val, "note": None if val is not None else "not set (engine default)"})
        return 0
    if "--files" in argv:
        exts = None
        if "--ext" in argv:
            exts = set(argv[argv.index("--ext") + 1].split(","))
        rest = [a for a in argv if not a.startswith("--") and (not exts or a != ",".join(sorted(exts)))]
        rest = [a for a in rest if "--ext" not in argv or a != argv[argv.index("--ext") + 1]]
        root = project_or_exit(rest[0] if rest else ".")
        files = sorted("res://" + p.relative_to(root).as_posix() for p in iter_files(root, exts))
        emit({"ok": True, "count": len(files), "files": files[:500]})
        return 0
    root = project_or_exit(argv[0] if argv else ".")
    emit(project_summary(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
