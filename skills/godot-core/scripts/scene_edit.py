#!/usr/bin/env python3
"""Create or edit .tscn scenes through Godot itself (never hand-write scene text).

Runs scene_edit.gd headless; autoload nodes are freed before _ready, so game code does not run.
Usage:
  python scene_edit.py SPEC.json [--project DIR]
  python scene_edit.py '{"scene":"res://x.tscn", ...}' [--project DIR]
Spec:
  {"scene": "res://player.tscn",                       # edited if it exists, else created
   "root": {"type": "CharacterBody3D", "name": "Player", "script": "res://player.gd", "props": {}},
   "inherits": "res://base.tscn",                      # optional: new inherited scene instead of root
   "dry_run": false,                                   # true: report the tree, don't save
   "ops": [
    {"op": "add", "parent": ".", "type": "CollisionShape3D", "name": "Col", "unique": true,
     "props": {"shape": {"new": "CapsuleShape3D", "radius": 0.4, "height": 1.8}, "position": [0, 0.9, 0]}},
    {"op": "instance", "parent": ".", "scene": "res://gun.tscn", "name": "Gun"},
    {"op": "set", "node": "Col", "props": {"disabled": true, "transform": "Transform3D()"}},
    {"op": "script", "node": ".", "path": "res://player.gd"},
    {"op": "connect", "from": "Area", "signal": "body_entered", "to": ".", "method": "_on_area_body_entered"},
    {"op": "disconnect" | "remove" | "rename" | "move" | "group", ...}]}
Values: JSON numbers/bools/arrays (vectors, colors) convert by the property's type; strings parse
as Godot literals ("Vector3(1, 2, 3)", "Color.RED") unless the property is a String; resources are
{"new": "Class", prop: value...}, {"load": "res://..."} or a "res://" string.
Output: {"ok", "scene", "created", "saved", "tree": [...], "errors": [...]}. Any error = nothing saved. Build C# first (cs_build.py) for .cs scripts.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, parse_messages, project_or_exit, run, runner  # noqa: E402


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    proj = None
    if "--project" in argv:
        i = argv.index("--project")
        proj = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    src = argv[0]
    try:
        spec = json.loads(src) if src.lstrip().startswith("{") else json.loads(open(src, encoding="utf-8").read())
    except (OSError, ValueError) as e:
        emit({"ok": False, "error": f"bad spec: {e}"}, 2)
    if not str(spec.get("scene", "")).startswith("res://"):
        emit({"ok": False, "error": "spec.scene must be a res:// path"}, 2)
    root = project_or_exit(proj or ".")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f)
        tmp = f.name
    try:
        r = run(["--script", runner(__file__, "scene_edit.gd"), "--", tmp], project=root, timeout=300)
    finally:
        os.unlink(tmp)
    line = next((ln for ln in r["out"].splitlines() if ln.startswith("RESULT_JSON ")), None)
    res = json.loads(line[len("RESULT_JSON "):]) if line else {"ok": False, "errors": ["runner produced no result"]}
    msgs = [m for m in parse_messages(r["out"] + "\n" + r["err"]) if "error" in m["type"]
            and "leaked" not in m["msg"]]
    if msgs:
        res["engine_errors"] = msgs[:20]
        res["ok"] = False
    emit(res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
