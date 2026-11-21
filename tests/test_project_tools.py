"""Tests for the project tools added in 1.1 (migrate_scan, addon_inspect, serve_web) and runtime checks
of data-only snippets (dungeon/cave generators, behavior tree, mod packs) on the real engine."""
import json
import re
import subprocess
import sys
import time
import urllib.request

from run_all import SKILLS, TMP, fixture, script
from test_snippets import FENCE


def _snippet(md_rel, heading):
    """Code of the first fenced block after a '## heading' line in skills/<md_rel>."""
    text = (SKILLS / md_rel).read_text("utf-8")
    start = text.index("## " + heading)
    return FENCE.search(text, start).group(2)


def test_migrate_scan_godot3_project():
    p = TMP / f"g3_{time.time_ns()}"
    (p / "scripts").mkdir(parents=True)
    (p / "project.godot").write_text('config_version=4\n\n[application]\nconfig/name="Old"\n', "utf-8")
    (p / "scripts" / "player.gd").write_text(
        "extends KinematicBody\nexport(int) var speed = 5\nonready var cam = $Camera\n\n"
        "func _physics_process(delta):\n\tvelocity = move_and_slide(velocity, Vector3.UP)\n"
        "\tyield(get_tree().create_timer(1), \"timeout\")\n", "utf-8")
    (p / "Enemy.cs").write_text("using Godot;\npublic class Enemy : Node\n{\n    [Signal] delegate void Hit(int d);\n}\n", "utf-8")
    (p / "m.shader").write_text("shader_type spatial;\nuniform vec4 c : hint_color;\n", "utf-8")
    (p / "a.tscn").write_text('[gd_scene load_steps=2 format=2]\n[node name="A" type="Spatial"]\n', "utf-8")
    r = script("godot-migration", "migrate_scan", p)
    assert not r["ok"] and r["project"]["godot"] == "3.x", r
    for rule in ("gd3-class-renames", "gd3-export", "gd3-onready", "gd3-move-and-slide-args", "gd3-yield",
                 "cs3-not-partial", "cs3-signal-delegate", "shader3-hint-color", "scene-format-2", "gd3-scene-types"):
        assert rule in r["by_rule"], (rule, r["by_rule"])
    assert not any(f["rule"] == "gd3-3d-suffix" for f in r["findings"]), "node path $Camera must not be flagged"
    d = script("godot-migration", "migrate_scan", p, "--convert")  # dry run through the engine converter
    assert d["mode"] == "dry-run" and "would be converted" in d["summary"], d
    assert any("CharacterBody3D" in c for c in d["changes"]), d["changes"]


def test_migrate_scan_clean_on_47_code():
    p = fixture("gd_project")
    (p / "snips").mkdir()
    ext = {"gdscript": ".gd", "csharp": ".cs", "gdshader": ".gdshader"}
    n = 0
    for md in sorted(SKILLS.glob("*/**/*.md")):
        for i, (lang, code) in enumerate(FENCE.findall(md.read_text("utf-8"))):
            if "snippet: skip" in code.splitlines()[0]:
                continue
            (p / "snips" / f"{md.parent.parent.name}_{md.stem}_{i}{ext[lang]}").write_text(code, "utf-8")
            n += 1
    r = script("godot-migration", "migrate_scan", p)
    assert n > 100 and r["errors"] == 0, [f for f in r["findings"] if f["severity"] == "error"][:10]


def test_addon_inspect_reports_and_toggles():
    p = fixture("gd_project")
    (p / "addons" / "good").mkdir(parents=True)
    (p / "addons" / "good" / "plugin.cfg").write_text('[plugin]\nname="Good"\nversion="1.2.3"\nscript="plugin.gd"\n', "utf-8")
    (p / "addons" / "good" / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", "utf-8")
    (p / "addons" / "ext").mkdir()
    (p / "addons" / "ext" / "ext.gdextension").write_text(
        '[configuration]\nentry_symbol="init"\ncompatibility_minimum="4.9"\n\n[libraries]\n'
        'windows.x86_64="res://addons/ext/missing.dll"\n', "utf-8")
    (p / "export_presets.cfg").write_text('[preset.0]\nname="Droid"\nplatform="Android"\n', "utf-8")
    r = script("godot-addons", "addon_inspect", p)
    by = {a["name"]: a for a in r["addons"]}
    assert not r["ok"] and by["good"]["version"] == "1.2.3" and not by["good"]["enabled"], r
    w = " | ".join(by["ext"]["warnings"])
    assert "needs Godot 4.9+" in w and "missing binary" in w and "'android'" in w, w
    e = script("godot-addons", "addon_inspect", p, "--enable", "good")
    assert e["ok"] and "res://addons/good/plugin.cfg" in e["enabled"]
    assert 'enabled=PackedStringArray("res://addons/good/plugin.cfg")' in (p / "project.godot").read_text("utf-8")
    assert script("godot-addons", "addon_inspect", p, "--disable", "good")["enabled"] == []


def test_serve_web_check_and_headers():
    d = TMP / f"web_{time.time_ns()}"
    d.mkdir()
    (d / "index.html").write_text("<script>const GODOT_THREADS_ENABLED = true;</script>", "utf-8")
    (d / "index.wasm").write_bytes(b"\0asm" + b"\0" * 1024)
    (d / "index.pck").write_bytes(b"GDPC")
    r = script("godot-mobile-web", "serve_web", d, "--check")
    assert r["ok"] and r["threads"] is True and any("COOP" in w for w in r["warnings"]), r
    port = 18060 + time.time_ns() % 500
    proc = subprocess.Popen([sys.executable, str(SKILLS / "godot-mobile-web" / "scripts" / "serve_web.py"), str(d),
                             "--port", str(port), "--seconds", "10"], stdout=subprocess.PIPE, text=True)
    try:
        assert json.loads(proc.stdout.readline())["url"].endswith("/index.html")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.wasm", timeout=5) as resp:
            assert resp.headers["Content-Type"] == "application/wasm"
            assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert resp.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    finally:
        proc.kill()


def test_data_snippets_run():
    """Generators, behavior tree, loot table and registry from the skills actually run (not just compile)."""
    p = fixture("gd_project")
    (p / "gen").mkdir()
    files = {
        "caves.gd": ("godot-procedural/references/patterns.md", "Cellular-automata caves"),
        "bsp.gd": ("godot-procedural/references/patterns.md", "BSP dungeon"),
        "poisson.gd": ("godot-procedural/references/patterns.md", "Poisson-disc scatter"),
        "loot.gd": ("godot-procedural/references/patterns.md", "Weighted loot table"),
        "bt.gd": ("godot-navigation-ai/references/patterns.md", "Minimal behavior tree"),
        "registry.gd": ("godot-modding-dlc/references/patterns.md", "Content registry"),
    }
    for name, (md, heading) in files.items():
        (p / "gen" / name).write_text(_snippet(md, heading), "utf-8")
    (p / "check.gd").write_text('''extends SceneTree

func _init() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var caves: Dictionary = load("res://gen/caves.gd").generate(rng, Vector2i(40, 30))
	var open := caves.values().count(false)
	var Bsp: GDScript = load("res://gen/bsp.gd")
	var ok_levels := 0
	for s in 20:
		var d = Bsp.new()
		d.build(s, Rect2i(0, 0, 80, 60))
		if d.rooms.size() >= 4 and d.is_connected_level():
			ok_levels += 1
	var pts: PackedVector2Array = load("res://gen/poisson.gd").poisson_disc(rng, Vector2(200, 200), 12.0)
	var min_d := INF
	for i in pts.size():
		for j in range(i + 1, pts.size()):
			min_d = minf(min_d, pts[i].distance_to(pts[j]))
	var loot = LootTable.new()
	loot.items.assign([&"sword", &"gold"])
	loot.weights = PackedFloat32Array([1.0, 3.0])
	var counts := {}
	for i in 400:
		var item: StringName = loot.roll(rng)
		counts[item] = counts.get(item, 0) + 1
	var seq := BTNode.Sequence.new([BTNode.Condition.new(func(_a, _b): return true), BTNode.Action.new(func(_a, _b): return BTNode.Status.RUNNING)])
	var sel := BTNode.Selector.new([BTNode.Condition.new(func(_a, _b): return false), seq])
	ContentRegistry.register(&"items", &"sword", 5)
	print("RESULT ", JSON.stringify({"open": open, "cells": caves.size(), "levels": ok_levels, "points": pts.size(),
		"min_d": min_d, "gold": counts.get(&"gold", 0), "sword": counts.get(&"sword", 0),
		"bt": sel.tick(null, {}), "reg": ContentRegistry.get_entry(&"items", &"sword")}))
	quit()
''', "utf-8")
    script("godot-core", "run_godot", "import", cwd=p)
    r = script("godot-core", "run_godot", "script", "check.gd", "--timeout", "120", cwd=p)
    line = next((ln for ln in r["stdout_tail"] if ln.startswith("RESULT ")), None) if isinstance(r["stdout_tail"], list) else \
        next((ln for ln in r["stdout_tail"].splitlines() if ln.startswith("RESULT ")), None)
    assert line, r
    res = json.loads(line[7:])
    assert res["cells"] == 1200 and 200 < res["open"] < 1100, res
    assert res["levels"] >= 18, res
    assert res["points"] > 80 and res["min_d"] >= 12.0, res
    assert res["gold"] > res["sword"] > 40, res
    assert res["bt"] == 2 and res["reg"] == 5, res  # RUNNING, registry round trip
    assert not [e for e in r.get("errors", []) if "error" in e.get("type", "")], r["errors"]


def test_mod_pack_round_trip():
    """PCKPacker builds a mod pack; load_resource_pack mounts it and the mod scene loads."""
    p = fixture("gd_project")
    (p / "make_and_load.gd").write_text('''extends SceneTree

func _init() -> void:
	var src := "user://mod_src.tscn"
	var root := Node2D.new()
	root.name = "ModRoot"
	var ps := PackedScene.new()
	ps.pack(root)
	ResourceSaver.save(ps, src)
	root.free()
	var cfg := ConfigFile.new()
	cfg.set_value("mod", "id", "demo")
	cfg.save("user://mod_src.cfg")
	var packer := PCKPacker.new()
	packer.pck_start("user://demo.pck")
	packer.add_file("res://mods/demo/level.tscn", src)
	packer.add_file("res://mods/demo/mod.cfg", "user://mod_src.cfg")
	var flushed := packer.flush()
	var mounted := ProjectSettings.load_resource_pack("user://demo.pck", false)
	var scene := load("res://mods/demo/level.tscn") as PackedScene
	var inst := scene.instantiate() if scene else null
	var c2 := ConfigFile.new()
	print("RESULT ", JSON.stringify({"flush": flushed, "mounted": mounted, "name": inst.name if inst else "",
		"cfg": c2.load("res://mods/demo/mod.cfg") == OK and c2.get_value("mod", "id") == "demo"}))
	if inst:
		inst.free()
	quit()
''', "utf-8")
    r = script("godot-core", "run_godot", "script", "make_and_load.gd", "--timeout", "120", cwd=p)
    tail = r["stdout_tail"] if isinstance(r["stdout_tail"], list) else r["stdout_tail"].splitlines()
    line = next((ln for ln in tail if ln.startswith("RESULT ")), None)
    assert line, r
    res = json.loads(line[7:])
    assert res == {"flush": 0, "mounted": True, "name": "ModRoot", "cfg": True}, res
