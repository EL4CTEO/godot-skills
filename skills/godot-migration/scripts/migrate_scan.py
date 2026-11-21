#!/usr/bin/env python3
"""Scan a Godot project for Godot 3 / older 4.x code that needs changes for 4.7 (static, no engine needed).

Usage:
  python migrate_scan.py [DIR] [--limit N] [--rule NAME]
      DIR defaults to the project at or above the current folder. Scans .gd, .cs, .csproj,
      .gdshader/.shader, .tscn/.tres and project.godot (addons/ and .godot/ skipped).
  python migrate_scan.py [DIR] --convert [--apply] [--max-kb 4000] [--max-lines 100000]
      Godot 3 projects only. Runs the engine's converter: dry run (--validate-conversion-3to4),
      or with --apply the real --convert-3to4, which rewrites files in place with NO backup:
      commit first.
Output: {"ok", "project": {"config_version", "godot", "csharp"}, "count", "by_rule", "findings": [{file, line, rule, fix}]}
ok is false when any "error" severity finding exists (code that will not compile or run on 4.7).
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit, project_or_exit, run  # noqa: E402

# Type positions only (extends X, is X, as X, : X, new X, <X>, X.new()), so node names and variables don't match.
TYPE_CTX = r"(?:\bextends\s+|\bis\s+|\bas\s+|:\s*|\bnew\s+|<|^\s*)(?=\w+(?:\.new\(|[\s>,)\]{;=]|$))"
# (rule, severity, file kinds, regex, fix). Severity: error = won't work in 4.7, warn = behavior change, info = review.
GD, CS, SH, SC, PJ, CP = "gd", "cs", "shader", "scene", "project", "csproj"
RULES = [
    # GDScript syntax (Godot 3)
    ("gd3-export", "error", {GD}, r"^\s*export(\(.*?\))?\s+var\b", "@export var x := ... (typed export annotations: @export_range, @export_enum, ...)"),
    ("gd3-onready", "error", {GD}, r"^\s*onready\s+var\b", "@onready var"),
    ("gd3-tool", "error", {GD}, r"^tool\s*$", "@tool"),
    ("gd3-setget", "error", {GD}, r"\bsetget\b", "var x: int: set = _set_x, get = _get_x (or inline set(v): / get:)"),
    ("gd3-yield", "error", {GD}, r"\byield\s*\(", "await obj.signal_name / await get_tree().create_timer(t).timeout"),
    ("gd3-connect-string", "error", {GD}, r"\.connect\(\s*\"[a-z_]+\"\s*,\s*\w+\s*,\s*\"", "sig.connect(obj.method) or sig.connect(method.bind(args))"),
    ("gd3-rpc-keywords", "error", {GD}, r"^\s*(remote|master|puppet|remotesync|mastersync|puppetsync)\s+func\b", "@rpc(\"any_peer\"|\"authority\", \"call_local\", \"reliable\") func"),
    ("gd3-funcref", "error", {GD}, r"\bfuncref\(", "a Callable: obj.method or Callable(obj, \"method\")"),
    ("gd3-pool-arrays", "error", {GD, CS}, r"\bPool(String|Int|Real|Byte|Vector2|Vector3|Color)Array\b", "Packed*Array (PoolRealArray -> PackedFloat32Array)"),
    ("gd3-instance", "error", {GD}, r"\.instance\(\)", ".instantiate()"),
    ("gd3-empty", "warn", {GD}, r"\.empty\(\)", ".is_empty()"),
    ("gd3-math-names", "error", {GD}, r"\b(deg2rad|rad2deg|rand_range|stepify|range_lerp|str2var|var2str|to_json|parse_json|lerp_angle_deg)\s*\(", "deg_to_rad, rad_to_deg, randf_range, snapped, remap, str_to_var, var_to_str, JSON.stringify, JSON.parse_string"),
    ("gd3-file-dir", "error", {GD}, r"\b(File|Directory)\.new\(\)", "FileAccess.open(path, FileAccess.READ) / DirAccess.open(path) (static, return null on error)"),
    ("gd3-os-time", "error", {GD}, r"\bOS\.(get_ticks_msec|get_ticks_usec|get_unix_time|get_datetime|get_system_time_msecs)\(", "Time.get_ticks_msec() / Time.get_unix_time_from_system() / Time.get_datetime_dict_from_system()"),
    ("gd3-os-window", "error", {GD}, r"\bOS\.(window_size|window_fullscreen|window_position|set_window_|window_maximized|vsync_enabled)", "get_window().size / DisplayServer.window_set_mode() / DisplayServer.window_set_vsync_mode()"),
    ("gd3-change-scene", "error", {GD}, r"(?<!func )\bchange_scene\(", "get_tree().change_scene_to_file(path) (or _to_packed / _to_node)"),
    ("gd3-update", "warn", {GD}, r"(^|\s|self\.)update\(\)\s*$", "queue_redraw() if this is a CanvasItem redraw"),
    ("gd3-move-and-slide-args", "error", {GD}, r"move_and_slide(_with_snap)?\(\s*[^)\s]", "set velocity/up_direction/floor_snap_length, then move_and_slide() with no arguments"),
    ("gd3-is-network-master", "error", {GD, CS}, r"\b(is_network_master|IsNetworkMaster|get_network_master|set_network_master)\b", "is_multiplayer_authority() / set_multiplayer_authority()"),
    ("gd3-scancode", "error", {GD}, r"\b(scancode|BUTTON_LEFT|BUTTON_RIGHT|BUTTON_WHEEL_UP|BUTTON_WHEEL_DOWN)\b", "keycode / physical_keycode, MOUSE_BUTTON_LEFT ..."),
    ("gd3-rect-props", "error", {GD}, r"\brect_(position|size|min_size|rotation|scale|pivot_offset|global_position)\b", "position, size, custom_minimum_size, rotation, scale, pivot_offset, global_position"),
    ("gd3-translation", "warn", {GD}, r"\.translation\b(?!_)", "position (Node3D) unless this is a Translation resource"),
    ("gd3-editor-hint", "error", {GD}, r"\bEngine\.editor_hint\b", "Engine.is_editor_hint()"),
    ("gd3-tween-node", "error", {GD}, r"\bTween\.new\(\)|\binterpolate_property\(", "var t := create_tween(); t.tween_property(node, \"prop\", value, time)"),
    # Node / class renames (any language)
    ("gd3-class-renames", "error", {GD, CS}, TYPE_CTX + r"(KinematicBody2D|KinematicBody|Spatial|Position2D|Position3D|VisibilityNotifier2D|VisibilityNotifier|ViewportContainer|GIProbe|BakedLightmap|ImmediateGeometry|ARVROrigin|ARVRCamera|ARVRServer|NetworkedMultiplayerENet|StreamTexture|YSort|Listener|ToolButton|Navigation|NavigationMeshInstance)\b|\b(VisualServer|Physics2DServer|ARVRServer)\.", "4.x names: CharacterBody2D/3D, Node3D, Marker2D/3D, VisibleOnScreenNotifier2D/3D, SubViewportContainer, VoxelGI, LightmapGI, ImmediateMesh, XROrigin3D, RenderingServer, PhysicsServer2D, XRServer, ENetMultiplayerPeer, CompressedTexture2D, y_sort_enabled, AudioListener3D, Button (flat), NavigationRegion3D"),
    ("gd3-3d-suffix", "error", {GD, CS}, TYPE_CTX + r"(MeshInstance|Camera|RayCast|Area|RigidBody|StaticBody|CollisionShape|Particles|CPUParticles|Skeleton|BoneAttachment|SpringArm|PathFollow|DirectionalLight|OmniLight|SpotLight)\b(?!2D|3D)", "add the 3D suffix (MeshInstance3D, Camera3D, Area3D, ...) and use GPUParticles3D"),
    ("gd3-sprite-light", "error", {GD, CS}, TYPE_CTX + r"(Sprite|AnimatedSprite|Light2D)\b(?!2D|3D)", "Sprite2D, AnimatedSprite2D, PointLight2D"),
    ("gd3-scene-types", "error", {SC}, r'type="(KinematicBody2D|KinematicBody|Spatial|Position2D|Position3D|Sprite|AnimatedSprite|Light2D|MeshInstance|Camera|RayCast|Area|RigidBody|StaticBody|CollisionShape|Particles|CPUParticles|Skeleton|Path|PathFollow|DirectionalLight|OmniLight|SpotLight|YSort|ViewportContainer|Navigation|NavigationMeshInstance|VisibilityNotifier|VisibilityNotifier2D|GIProbe|BakedLightmap|Listener)"', "Godot 3 node type in a scene: open in the 4.7 editor (or --convert-3to4) so types are renamed"),
    # Deprecated in 4.x
    ("tilemap-deprecated", "warn", {GD, CS, SC}, r"\bTileMap\b(?!Layer|Pattern)", "one TileMapLayer per layer (TileMap bottom panel: extract layers as TileMapLayer nodes)"),
    ("parallax-deprecated", "warn", {GD, CS, SC}, r"\b(ParallaxBackground|ParallaxLayer)\b", "Parallax2D"),
    ("skeleton-ik-deprecated", "warn", {GD, CS, SC}, r"\bSkeletonIK3D\b", "IK framework (4.6+): TwoBoneIK3D, FABRIK3D, CCDIK3D, SplineIK3D"),
    # 4.x -> 4.7 behavior changes
    ("rpc-config-rename", "error", {GD, CS}, r"\b(get_rpc_config|GetRpcConfig)\b", "get_node_rpc_config (4.5)"),
    ("duplicate-deep", "info", {GD}, r"\.duplicate\(\s*true\s*\)", "4.5+: duplicate(true) no longer copies external sub-resources; use duplicate_deep() if you need that"),
    ("get-as-text-arg", "error", {GD, CS}, r"\b(get_as_text|GetAsText)\(\s*(true|false)", "FileAccess.get_as_text() lost its skip_cr argument (4.6)"),
    ("blendspace-sync", "error", {GD, CS, SC}, r"\b(BlendSpace[12]D\w*\.sync\b|\bsync = (true|false)\b)", "BlendSpace sync (bool) became sync_mode (enum) in 4.7"),
    ("device-zero-keyboard", "info", {GD, CS}, r"\.(device|Device)\s*==\s*0\b", "4.7: keyboard/mouse events use InputEvent.DEVICE_ID_KEYBOARD / DEVICE_ID_MOUSE, not 0"),
    ("tcp-moved", "info", {CS}, r"\b(StreamPeerTcp|TcpServer)\b", "4.6 moved poll/get_status/is_connection_available to StreamPeerSocket/SocketServer: rebuild C#"),
    ("cs-animation-length", "warn", {CS}, r"\bfloat\s+\w+\s*=\s*\w+\.Length\b", "4.7: Animation.Length is double"),
    ("cs-current-animation", "warn", {CS}, r"\.(CurrentAnimation|AssignedAnimation|Autoplay)\s*==\s*\"", "4.6: these are StringName in C#; compare with new StringName(...) or .ToString()"),
    # C# Godot 3 -> 4
    ("cs3-godot-object", "error", {CS}, r"\bGodot\.Object\b|:\s*Object\b|\bReference\b(?=\s*[{,]|\s*$)", "GodotObject / RefCounted"),
    ("cs3-not-partial", "error", {CS}, r"^\s*(public\s+)?(sealed\s+)?class\s+\w+\s*:\s*(Node|Node2D|Node3D|Control|Resource|CharacterBody\w*|RigidBody\w*|Area\w*|Sprite2D|GodotObject|RefCounted)\b", "Godot classes must be 'partial' (public partial class X : Node)"),
    ("cs3-signal-delegate", "error", {CS}, r"\[Signal\]\s*(public\s+)?delegate\s+void\s+\w+(?<!EventHandler)\s*\(", "signal delegates must end in EventHandler: [Signal] public delegate void HitEventHandler(int dmg)"),
    ("cs3-string-connect", "error", {CS}, r"\.Connect\(\s*(\"\w+\"|nameof\(\w+\))\s*,\s*this\s*,", "Godot 3 Connect(signal, target, method): use C# events (Hit += OnHit) or Connect(SignalName.Hit, Callable.From(...))"),
    ("cs3-instance", "error", {CS}, r"\.Instance(<\w+>)?\(\)", ".Instantiate<T>()"),
    ("cs3-float-delta", "error", {CS}, r"override void _(Physics)?Process\(\s*float\s+delta", "_Process(double delta)"),
    ("cs3-os-ticks", "error", {CS}, r"\bOS\.GetTicks(Msec|Usec)\b", "Time.GetTicksMsec()"),
    # Shaders
    ("shader3-hint-color", "error", {SH}, r"\bhint_color\b", "source_color"),
    ("shader3-matrices", "error", {SH}, r"\b(WORLD_MATRIX|CAMERA_MATRIX|INV_CAMERA_MATRIX|NORMALMAP|NORMALMAP_DEPTH|TRANSMISSION|WORLD_NORMAL_MATRIX)\b", "MODEL_MATRIX, INV_VIEW_MATRIX, VIEW_MATRIX, NORMAL_MAP, NORMAL_MAP_DEPTH, BACKLIGHT, MODEL_NORMAL_MATRIX"),
    ("shader3-screen-depth", "error", {SH}, r"\b(SCREEN_TEXTURE|DEPTH_TEXTURE|NORMAL_ROUGHNESS_TEXTURE)\b", "declare uniform sampler2D screen_tex : hint_screen_texture (hint_depth_texture, hint_normal_roughness_texture)"),
    ("shader3-alpha-scissor", "error", {SH}, r"\bALPHA_SCISSOR\b(?!_)", "ALPHA_SCISSOR_THRESHOLD"),
    ("shader3-render-mode", "error", {SH}, r"\b(depth_draw_alpha_prepass|vertex_lighting|async_visible|async_hidden)\b", "depth_prepass_alpha; per-vertex lighting is a project setting; async modes were removed"),
    # Files
    ("scene-format-2", "error", {SC}, r"^\[gd_(scene|resource)\b[^\]]*\bformat=2\b", "Godot 3 file: open the project in the 4.7 editor or run --convert-3to4"),
    ("csproj-sdk-old", "warn", {CP}, r"Godot\.NET\.Sdk/(3\.|4\.[0-6]\b)", "Sdk=\"Godot.NET.Sdk/4.7.2\" and TargetFramework net8.0 (Android export also needs net9.0)"),
    ("csproj-godot3", "error", {CP}, r"Godot\.NET\.Sdk/3\.|<Reference Include=\"GodotSharp\"", "Godot 3 C# project: regenerate the csproj from the 4.7 editor (Project > Tools > C# > Create C# solution)"),
]
KIND = {".gd": GD, ".cs": CS, ".gdshader": SH, ".shader": SH, ".tscn": SC, ".tres": SC, ".csproj": CP}
COMPILED = [(n, s, k, re.compile(rx), fix) for n, s, k, rx, fix in RULES]
COMMENT = {GD: "#", CS: "//", SH: "//", SC: ";", CP: "<!--"}


def project_facts(root):
    text = (root / "project.godot").read_text("utf-8", "replace")
    cv = re.search(r"^config_version=(\d+)", text, re.M)
    feats = re.search(r'^config/features=PackedStringArray\(([^)]*)\)', text, re.M)
    cv = int(cv.group(1)) if cv else None
    ver = None
    if feats:
        m = re.search(r'"(\d+\.\d+)"', feats.group(1))
        ver = m.group(1) if m else None
    godot = "3.x" if cv == 4 else (ver or "4.x") if cv == 5 else "unknown"
    csharp = any(root.glob("*.csproj")) or "[mono]" in text or "dotnet/project/assembly_name" in text
    return {"config_version": cv, "godot": godot, "csharp": csharp}


def scan(root, only=None):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".") and d not in ("addons", "bin", "obj")]
        for fn in fns:
            kind = KIND.get(pathlib.Path(fn).suffix)
            if not kind:
                continue
            f = pathlib.Path(dp) / fn
            try:
                lines = f.read_text("utf-8", "replace").splitlines()
            except OSError:
                continue
            rel = "res://" + f.relative_to(root).as_posix()
            for i, line in enumerate(lines, 1):
                if line.lstrip().startswith(COMMENT[kind]):
                    continue
                for name, sev, kinds, rx, fix in COMPILED:
                    if kind in kinds and (not only or name == only) and rx.search(line):
                        out.append({"file": rel, "line": i, "rule": name, "severity": sev, "code": line.strip()[:140], "fix": fix})
    return out


def convert(root, apply, max_kb, max_lines):
    flag = "--convert-3to4" if apply else "--validate-conversion-3to4"
    r = run([flag, str(max_kb), str(max_lines)], project=root, timeout=1800, headless=True)
    text = (r["out"] + "\n" + r["err"]).strip().splitlines()
    summary = next((ln.strip() for ln in reversed(text) if "all files(" in ln), "")
    changes, cur = [], ""
    for ln in text:
        m = re.search(r'conversion - \d+/\d+ file - "([^"]+)"', ln)
        if m:
            cur = m.group(1)
        elif " -> " in ln or "=====>" in ln or "will be renamed" in ln:
            changes.append(f"{cur}: {ln.strip()}"[:300])
    errors = [ln.strip() for ln in text if ln.startswith("ERROR") and "PCRE2" not in ln]
    return {"ok": r["rc"] == 0 and not errors, "mode": "apply" if apply else "dry-run", "rc": r["rc"],
            "summary": summary, "changes": changes[:200], "change_count": len(changes), "errors": errors[:20]}


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    args = [a for a in argv if not a.startswith("--")]
    opt = lambda k, d: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else d  # noqa: E731
    vals = {opt(k, None) for k in ("--limit", "--rule", "--max-kb", "--max-lines")}
    dirs = [a for a in args if a not in vals]
    root = project_or_exit(dirs[0] if dirs else ".")
    facts = project_facts(root)
    if "--convert" in argv:
        if facts["config_version"] != 4:
            emit({"ok": False, "project": facts, "error": "--convert is only for Godot 3 projects (config_version=4)"}, 1)
        res = convert(root, "--apply" in argv, int(opt("--max-kb", 4000)), int(opt("--max-lines", 100000)))
        res["project"] = facts
        emit(res)
        return 0 if res["ok"] else 1
    found = scan(root, opt("--rule", None))
    by_rule = {}
    for f in found:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    limit = int(opt("--limit", 200))
    errors = sum(1 for f in found if f["severity"] == "error")
    emit({"ok": errors == 0, "project": facts, "count": len(found), "errors": errors,
          "by_rule": dict(sorted(by_rule.items(), key=lambda kv: -kv[1])), "findings": found[:limit],
          "truncated": len(found) > limit})
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
