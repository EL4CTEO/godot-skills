"""Every ```gdscript, ```csharp and ```gdshader block in skills/**/*.md must compile on the real engine.

GDScript blocks are full scripts checked with gd_check (fixture autoload `Events` available).
C# blocks are full files built inside the C# fixture; a file-scoped namespace is added when the
block has none, so class names can repeat across snippets. Opt out with a first line
`# snippet: skip` / `// snippet: skip` (only for intentionally broken examples).
"""
import re
import shutil

from run_all import SKILLS, dotnet, fixture, gdunit_addon, script

FENCE = re.compile(r"^```(gdscript|csharp|gdshader)[ \t]*\n(.*?)^```", re.S | re.M)


def blocks(lang):
    out = []
    for md in sorted(SKILLS.glob("*/**/*.md")):
        for i, (lg, code) in enumerate(FENCE.findall(md.read_text("utf-8"))):
            if lg == lang and "snippet: skip" not in code.splitlines()[0]:
                out.append((md, i, code))
    return out


def _name(md, i):
    rel = md.relative_to(SKILLS).with_suffix("").as_posix()
    return re.sub(r"[^A-Za-z0-9]+", "_", rel) + f"_{i}"


def test_gdscript_snippets_compile():
    snippets = blocks("gdscript")
    assert snippets, "no gdscript snippets found"
    p = fixture("gd_project")
    try:
        shutil.copytree(gdunit_addon(), p / "addons" / "gdUnit4")
    except Exception:  # offline: GdUnit snippets will fail and say so
        pass
    names = {}
    for md, i, code in snippets:
        m = re.search(r"^class_name (\w+)", code, re.M)
        if m:
            assert m.group(1) not in names, f"duplicate class_name {m.group(1)} in {md} and {names[m.group(1)]}"
            names[m.group(1)] = md
        (p / "snippets").mkdir(exist_ok=True)
        (p / "snippets" / f"{_name(md, i)}.gd").write_text(code, "utf-8")
    r = script("godot-gdscript", "gd_check", "snippets", cwd=p, timeout=1800)
    assert r["ok"], "\n".join(f'{e["file"]}:{e["line"]}: {e["msg"]}' for e in r["errors"])


def test_gdshader_snippets_compile():
    snippets = blocks("gdshader")
    assert snippets, "no gdshader snippets found"
    p = fixture("gd_project")
    (p / "shaders").mkdir()
    for md, i, code in snippets:
        (p / "shaders" / f"{_name(md, i)}.gdshader").write_text(code, "utf-8")
    r = script("godot-shaders-vfx", "shader_check", "shaders", cwd=p)
    assert r["ok"], "\n".join(f'{e["file"]}:{e["line"]}: {e["msg"]}' for e in r["errors"]) or r


def test_csharp_snippets_compile():
    dotnet()
    snippets = blocks("csharp")
    assert snippets, "no csharp snippets found"
    p = fixture("cs_project")
    (p / "Snippets").mkdir()
    for md, i, code in snippets:
        name = _name(md, i)
        if not re.search(r"^\s*namespace\s", code, re.M):
            lines = code.splitlines()
            last_using = max((k for k, ln in enumerate(lines) if ln.startswith("using ")), default=-1)
            lines.insert(last_using + 1, f"namespace Snippets.{name};")
            code = "\n".join(lines) + "\n"
        (p / "Snippets" / f"{name}.cs").write_text(code, "utf-8")
    r = script("godot-csharp", "cs_build", cwd=p, timeout=1800)
    assert r["ok"], "\n".join(f'{e["file"]}:{e["line"]}: {e["code"]} {e["msg"]}' for e in r["errors"]) or r
