import shutil

from run_all import dotnet, fixture, gdunit_addon, script

PRESET = """[preset.0]

name="Linux"
platform="Linux"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/linux/game.x86_64"

[preset.0.options]

binary_format/embed_pck=false
"""


def test_export_list_and_pack():
    p = fixture("gd_project")
    (p / "export_presets.cfg").write_text(PRESET, "utf-8")
    r = script("godot-export-ci", "export", "--list", cwd=p)
    assert r["presets"][0]["name"] == "Linux" and "installed" in r["templates"]
    r = script("godot-export-ci", "export", "Linux", "--pack", "--out", "build/game.pck", cwd=p)
    assert r["ok"] and r["bytes"] > 1000, r


def test_gdunit_gdscript_tests():
    addon = gdunit_addon()
    p = fixture("gd_project")
    shutil.copytree(addon, p / "addons" / "gdUnit4")
    r = script("godot-testing-debug", "test_run", cwd=p)
    assert r["ok"] and r["gd"]["total"] == 1, r
    (p / "test" / "fail_test.gd").write_text(
        "extends GdUnitTestSuite\n\n\nfunc test_fails() -> void:\n\tassert_int(1 + 1).is_equal(3)\n", "utf-8")
    r = script("godot-testing-debug", "test_run", cwd=p)
    f = r["gd"]["failures"]
    assert not r["ok"] and f[0]["file"] == "res://test/fail_test.gd" and f[0]["line"] == 5, r


def test_documented_test_suites_pass():
    """The GdUnit/gdUnit4Net examples in godot-testing-debug must not just compile: they must pass."""
    import re
    from run_all import SKILLS
    md = (SKILLS / "godot-testing-debug" / "references" / "patterns.md").read_text("utf-8")
    gd = [b for b in re.findall(r"```gdscript\n(.*?)```", md, re.S) if "extends GdUnitTestSuite" in b]
    p = fixture("gd_project")
    shutil.copytree(gdunit_addon(), p / "addons" / "gdUnit4")
    for i, code in enumerate(gd):
        (p / "test" / f"doc{i}_test.gd").write_text(code, "utf-8")
    r = script("godot-testing-debug", "test_run", cwd=p)
    assert r["ok"] and r["gd"]["total"] >= 1 + len(gd), r
    try:
        dotnet()
    except Exception:
        return
    cs = [b for b in re.findall(r"```csharp\n(.*?)```", md, re.S) if "[TestSuite]" in b]
    c = fixture("cs_project")
    for i, code in enumerate(cs):
        (c / "test" / f"DocTest{i}.cs").write_text(code, "utf-8")
    r = script("godot-testing-debug", "test_run", "--cs", cwd=c)
    assert r["ok"] and r["cs"]["failed"] == 0 and r["cs"]["total"] >= 2, r


def test_gdunit4net_csharp_tests():
    dotnet()
    p = fixture("cs_project")
    r = script("godot-testing-debug", "test_run", "--cs", cwd=p)
    assert r["ok"] and r["cs"]["total"] == 1 and r["cs"]["passed"] == 1, r
