from run_all import fixture, script


def test_api_lookup_member_and_csharp_name():
    r = script("godot-core", "api_lookup", "Tween.tween_await")
    assert r["ok"] and r["gd"].startswith("tween_await(signal: Signal)") and "Tween.TweenAwait(Signal)" in r["cs"]
    r = script("godot-core", "api_lookup", "GpuParticles2D.Restart")  # C# names resolve too
    assert r["class"] == "GPUParticles2D" and r["name"] == "restart"


def test_api_lookup_globals_settings_annotations():
    assert script("godot-core", "api_lookup", "lerp")["class"] == "@GlobalScope"
    assert script("godot-core", "api_lookup", "range")["class"] == "@GDScript"
    assert script("godot-core", "api_lookup", "@export_range")["kind"] == "annotation"
    r = script("godot-core", "api_lookup", "ProjectSettings.physics/3d/physics_engine")
    assert r["ok"] and '"DEFAULT"' in r["gd"]


def test_api_lookup_flags_deprecated_and_misses():
    r = script("godot-core", "api_lookup", "TileMap")
    assert "TileMapLayer" in r.get("deprecated", "")
    r = script("godot-core", "api_lookup", "Node3D.translation")
    assert not r["ok"] and r["did_you_mean"] is not None


def test_project_inspect_summary_and_scene():
    p = fixture("gd_project")
    r = script("godot-core", "project_inspect", p)
    assert r["autoloads"] == {"Events": "res://autoload/events.gd"}
    assert r["input"]["jump"] == ["Space", "JoyA"] and r["input"]["move_left"] == ["A", "JoyLX-"]
    assert r["physics_3d"] == "Jolt Physics" and r["stretch"]["mode"] == "canvas_items"
    t = script("godot-core", "project_inspect", "--scene", "res://scenes/main.tscn", cwd=p)
    assert t["tree"][0] == "Main (Node2D) script=res://scripts/main.gd" and t["nodes"] == 3


def test_smoke_runs_main_scene():
    p = fixture("gd_project")
    r = script("godot-core", "run_godot", "smoke", "--frames", "5", cwd=p)
    assert r["ok"], r
    assert "GD_FIXTURE_READY 10" in r["stdout_tail"]


def test_smoke_reports_runtime_errors():
    p = fixture("gd_project")
    (p / "scripts" / "main.gd").write_text(
        "extends Node2D\n\nfunc _ready() -> void:\n\tvar n: Label = get_node(\"Missing\")\n\tn.text = \"x\"\n", "utf-8")
    r = script("godot-core", "run_godot", "smoke", "--frames", "5", cwd=p)
    assert not r["ok"] and any(e.get("file") == "res://scripts/main.gd" for e in r["errors"]), r


def test_scene_edit_create_edit_and_atomic_errors():
    p = fixture("gd_project")
    spec = ('{"scene":"res://scenes/player.tscn","root":{"type":"CharacterBody3D","name":"Player"},"ops":['
            '{"op":"add","parent":".","type":"CollisionShape3D","name":"Col","unique":true,'
            '"props":{"shape":{"new":"CapsuleShape3D","radius":0.4,"height":1.8},"position":[0,0.9,0]}},'
            '{"op":"add","parent":".","type":"Area3D","name":"Hurtbox"},'
            '{"op":"connect","from":"Hurtbox","signal":"body_entered","to":".","method":"_on_hurtbox_body_entered"},'
            '{"op":"add","parent":".","type":"Label3D","name":"Tag","props":{"modulate":"Color.RED","position":"Vector3.UP * 2"}}]}')
    r = script("godot-core", "scene_edit", spec, cwd=p)
    assert r["ok"] and r["saved"] and len(r["tree"]) == 4, r
    text = (p / "scenes" / "player.tscn").read_text("utf-8")
    assert 'uid="uid://' in text and "radius = 0.4" in text and "modulate = Color(1, 0, 0, 1)" in text
    assert '[connection signal="body_entered" from="Hurtbox" to="." method="_on_hurtbox_body_entered"]' in text
    bad = '{"scene":"res://scenes/player.tscn","ops":[{"op":"rename","node":"Tag","name":"T2"},{"op":"set","node":"Col","props":{"position":"hello"}}]}'
    r = script("godot-core", "scene_edit", bad, cwd=p)
    assert not r["ok"] and not r["saved"]
    assert "Tag" in (p / "scenes" / "player.tscn").read_text("utf-8")  # nothing saved on error
    inst = '{"scene":"res://scenes/level.tscn","root":{"type":"Node3D"},"ops":[{"op":"instance","parent":".","scene":"res://scenes/player.tscn","name":"P1"}]}'
    r = script("godot-core", "scene_edit", inst, cwd=p)
    assert r["ok"] and "[inst res://scenes/player.tscn]" in r["tree"][1]


def test_scene_edit_script_using_autoload_attaches():
    p = fixture("gd_project")
    spec = '{"scene":"res://scenes/m2.tscn","root":{"type":"Node2D","script":"res://scripts/main.gd"}}'
    r = script("godot-core", "scene_edit", spec, cwd=p)
    assert r["ok"] and "script=res://scripts/main.gd" in r["tree"][0], r
    wrong = '{"scene":"res://scenes/m3.tscn","root":{"type":"Node3D","script":"res://scripts/main.gd"}}'
    assert not script("godot-core", "scene_edit", wrong, cwd=p)["ok"]
