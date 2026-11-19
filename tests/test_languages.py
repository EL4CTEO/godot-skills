from run_all import dotnet, fixture, script


def test_gd_check_clean_and_errors():
    p = fixture("gd_project")
    r = script("godot-gdscript", "gd_check", "scripts", "autoload", cwd=p)
    assert r["ok"] and r["checked"] == 3, r
    (p / "scripts" / "bad.gd").write_text(
        'extends Node\n\nfunc _ready() -> void:\n\tvar x: int = "s"\n\tEvents.score_changed.emit(1)\n\tfoo()\n', "utf-8")
    r = script("godot-gdscript", "gd_check", "scripts", cwd=p)
    lines = sorted(e["line"] for e in r["errors"])
    assert not r["ok"] and lines == [4, 6], r  # autoload use on line 5 is valid


def test_cs_build_init_doctor_errors():
    dotnet()
    p = fixture("cs_project")
    r = script("godot-csharp", "cs_build", "--doctor", cwd=p)
    assert r["ok"] and r["sdk_version"] == r["engine"], r
    r = script("godot-csharp", "cs_build", cwd=p)
    assert r["ok"] and r["error_count"] == 0, r
    (p / "scripts" / "Bad.cs").write_text("using Godot;\npublic partial class Bad : Node { void F() { int x = \"s\"; } }\n", "utf-8")
    r = script("godot-csharp", "cs_build", cwd=p)
    assert not r["ok"] and r["errors"][0]["code"] == "CS0029" and r["errors"][0]["file"] == "res://scripts/Bad.cs", r


def test_cs_init_matches_editor_template():
    dotnet()
    p = fixture("gd_project")
    r = script("godot-csharp", "cs_build", "--init", cwd=p)
    assert r["ok"] and r["sdk"].startswith("Godot.NET.Sdk/4."), r
    text = (p / "GdFixture.csproj").read_text("utf-8")
    assert "<TargetFramework>net8.0</TargetFramework>" in text and "net9.0" in text and "EnableDynamicLoading" in text
    (p / "scripts" / "Hello.cs").write_text("using Godot;\npublic partial class Hello : Node { }\n", "utf-8")
    assert script("godot-csharp", "cs_build", cwd=p)["ok"]


def test_cs_smoke_after_build():
    dotnet()
    p = fixture("cs_project")
    assert script("godot-csharp", "cs_build", cwd=p)["ok"]
    r = script("godot-core", "run_godot", "smoke", "--frames", "5", cwd=p)
    assert r["ok"] and "CS_FIXTURE_READY Score: 10" in r["stdout_tail"], r
