from run_all import fixture, script


def test_shader_check_reports_errors_and_includes():
    p = fixture("gd_project")
    (p / "fx").mkdir()
    (p / "fx" / "ok.gdshader").write_text(
        "shader_type spatial;\nstencil_mode write, compare_always, 1;\nvoid fragment() { ALBEDO = vec3(1.0); }\n", "utf-8")
    (p / "fx" / "lib.gdshaderinc").write_text("vec3 tintify(vec3 c) { return c * nope; }\n", "utf-8")
    (p / "fx" / "inc.gdshader").write_text(
        'shader_type spatial;\n#include "res://fx/lib.gdshaderinc"\nvoid fragment() { ALBEDO = tintify(vec3(1.0)); }\n', "utf-8")
    (p / "fx" / "bad.gdshader").write_text("shader_type canvas_item;\nrender_mode nope_mode;\nvoid fragment() {}\n", "utf-8")
    r = script("godot-shaders-vfx", "shader_check", "fx", cwd=p)
    found = {(e["file"], e["line"]) for e in r["errors"]}
    assert not r["ok"] and r["checked"] == 3, r
    assert found == {("res://fx/lib.gdshaderinc", 1), ("res://fx/bad.gdshader", 2)}, r
