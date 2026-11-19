#!/usr/bin/env python3
"""Exact Godot API lookup from YOUR installed engine (GDScript + C# names). No docs in context.

Builds a cached index from `godot --dump-extension-api-with-docs` (+ GodotSharp.xml on .NET
builds) on first use, then answers in compact JSON.

Usage:
  python api_lookup.py Node3D                 class: inherits chain, brief, member names
  python api_lookup.py Node3D.look_at         member: GDScript + C# signature, description
  python api_lookup.py GpuParticles2D.Restart  C# names work too
  python api_lookup.py Vector3.lerp | lerp    builtin types, @GlobalScope utility functions
  python api_lookup.py @export_range | preload   GDScript annotations and built-in functions
  python api_lookup.py ProjectSettings.physics/3d/physics_engine   project setting: type + default
  python api_lookup.py --search await         find members whose name contains/regex-matches
  flags: --full (whole description + code example)  --lang cs|gd (example language, default gd)
         --rebuild (refresh cache)  --limit N (search results, default 40)
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import cache_dir, emit, godot_or_exit, version  # noqa: E402

CS_TYPES = {"System.Single": "float", "System.Double": "double", "System.Int32": "int", "System.Int64": "long",
            "System.Boolean": "bool", "System.String": "string", "System.Byte": "byte", "System.UInt32": "uint",
            "System.UInt64": "ulong", "System.Int16": "short", "System.Object": "object", "System.Void": "void"}


def key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def plain(text, full=False, lang="gd"):
    """Godot BBCode doc text -> compact plain text."""
    if not text:
        return ""
    want = "csharp" if lang == "cs" else "gdscript"
    def blocks(m):
        if not full:
            return ""
        inner = m.group(1)
        sel = re.search(rf"\[{want}[^\]]*\](.*?)\[/{want}\]", inner, re.S)
        code = sel.group(1) if sel else inner
        return "\n```\n" + code.strip("\n") + "\n```\n"
    t = re.sub(r"\[codeblocks\](.*?)\[/codeblocks\]", blocks, text, flags=re.S)
    t = re.sub(r"\[codeblock[^\]]*\](.*?)\[/codeblock\]", lambda m: blocks(m), t, flags=re.S)
    t = re.sub(r"\[(?:method|member|signal|constant|enum|param|annotation|theme_item|operator|constructor) ([^\]]+)\]", r"\1", t)
    t = re.sub(r"\[url=[^\]]*\](.*?)\[/url\]", r"\1", t)
    t = re.sub(r"\[/?(?:code|kbd)\]", "`", t)
    t = re.sub(r"\[/?(?:b|i|u|s|center|br)\]", "", t)
    t = t.replace("[lb]", "\x02").replace("[rb]", "\x03")  # escaped brackets: Array[lb]int[rb]
    t = re.sub(r"(?<![A-Za-z0-9_])\[([A-Za-z@][A-Za-z0-9_.]*)\]", r"\1", t)  # [Node] -> Node
    t = t.replace("\x02", "[").replace("\x03", "]")
    t = re.sub(r"\n{2,}", "\n", t).strip()
    if not full:
        first = t.split("\n")[0]
        notes = [ln for ln in t.split("\n")[1:] if ln.startswith(("Note:", "Warning:"))][:2]
        t = " ".join([first, *notes])
        if len(t) > 600:
            t = t[:597] + "..."
    return t


def gd_sig(name, m, kind="method"):
    args = []
    for a in m.get("arguments", []):
        s = f"{a['name']}: {a['type']}"
        if "default_value" in a:
            s += f" = {a['default_value']}"
        args.append(s)
    if m.get("is_vararg"):
        args.append("...")
    ret = m.get("return_value", {}).get("type") or m.get("return_type") or "void"
    pre = ("static " if m.get("is_static") else "") + ("virtual " if m.get("is_virtual") else "")
    post = " const" if m.get("is_const") else ""
    if kind == "signal":
        return f"signal {name}({', '.join(args)})"
    return f"{pre}{name}({', '.join(args)}) -> {ret}{post}"


def cs_type(t):
    t = t.replace("{", "<").replace("}", ">")
    t = re.sub(r"System\.Nullable<([^<>]+)>", r"\1?", t)
    t = re.sub(r"`\d+", "", t)
    for k, v in CS_TYPES.items():
        t = t.replace(k, v)
    t = re.sub(r"\bGodot\.Collections\.", "", t)
    return re.sub(r"\bGodot\.", "", t).replace("System.", "")


def split_args(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "{<":
            depth += 1
        elif ch in "}>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def find_cs_xml(exe):
    d = pathlib.Path(exe).resolve().parent
    for c in (d / "GodotSharp/Api/Release/GodotSharp.xml", d.parent / "Resources/GodotSharp/Api/Release/GodotSharp.xml",
              d / "GodotSharp/Api/Debug/GodotSharp.xml"):
        if c.is_file():
            return c
    return None


def build_index(exe, path):
    tmp = path.parent / "dump"
    tmp.mkdir(parents=True, exist_ok=True)
    r = run(["--dump-extension-api-with-docs"], exe=exe, timeout=300, headless=True, project=None) \
        if False else _dump(exe, tmp)
    api = json.loads((tmp / "extension_api.json").read_text("utf-8"))
    idx = {"version": api["header"]["version_full_name"], "classes": {}, "cs": {}}
    singletons = {s["name"] for s in api.get("singletons", [])}
    for c in api["classes"]:
        idx["classes"][c["name"]] = {
            "kind": "class", "inherits": c.get("inherits"), "brief": c.get("brief_description", ""),
            "desc": c.get("description", ""), "singleton": c["name"] in singletons,
            "instantiable": c.get("is_instantiable", True), "api_type": c.get("api_type"),
            "methods": {m["name"]: m for m in c.get("methods", [])},
            "properties": {p["name"]: p for p in c.get("properties", [])},
            "signals": {s["name"]: s for s in c.get("signals", [])},
            "enums": {e["name"]: e for e in c.get("enums", [])},
            "constants": {k["name"]: k for k in c.get("constants", [])},
        }
    for b in api["builtin_classes"]:
        idx["classes"][b["name"]] = {
            "kind": "builtin", "inherits": None, "brief": b.get("brief_description", ""), "desc": b.get("description", ""),
            "methods": {m["name"]: m for m in b.get("methods", [])},
            "properties": {p["name"]: p for p in b.get("members", [])},
            "signals": {}, "enums": {e["name"]: e for e in b.get("enums", [])},
            "constants": {k["name"]: k for k in b.get("constants", [])},
            "constructors": [", ".join(f"{a['name']}: {a['type']}" for a in c.get("arguments", []))
                             for c in b.get("constructors", [])],
        }
    idx["classes"]["@GlobalScope"] = {
        "kind": "global", "inherits": None, "brief": "Global utility functions, enums and constants.", "desc": "",
        "methods": {u["name"]: u for u in api["utility_functions"]}, "properties": {}, "signals": {},
        "enums": {e["name"]: e for e in api["global_enums"]},
        "constants": {k["name"]: k for k in api.get("global_constants", [])},
    }
    merge_doctool(exe, tmp, idx)
    xml = find_cs_xml(exe)
    for xf in ([xml, xml.with_name("GodotSharpEditor.xml")] if xml else []):
        if not xf.is_file():
            continue
        txt = xf.read_text("utf-8", errors="replace")
        for kind, full in re.findall(r'<member name="([TMPFE]):Godot\.([^"]+)"', txt):
            if kind == "T":
                idx["cs"].setdefault(full, [])
                continue
            mm = re.match(r"([A-Za-z0-9_.]+?)\.([A-Za-z0-9_]+)(\((.*)\))?$", full)
            if not mm:
                continue
            idx["cs"].setdefault(mm.group(1), []).append([kind, mm.group(2), mm.group(4)])
    path.write_text(json.dumps(idx, separators=(",", ":")), "utf-8")
    return idx


def fetch_official_docs(idx, dest):
    """Official class XML for this exact engine tag (descriptions + deprecated/experimental flags).

    Sparse git checkout (~16 MB, seconds); falls back to downloading the two most important files.
    Returns the list of XML files (empty when offline).
    """
    tag = re.match(r"Godot Engine v(\d+\.\d+(?:\.\d+)?)\.(\w+)", idx["version"])
    if not tag:
        return []
    ref = f"{tag.group(1)}-{tag.group(2)}"  # git tag, e.g. 4.7.2-stable
    if not any(dest.rglob("*.xml")) and shutil.which("git"):
        shutil.rmtree(dest, ignore_errors=True)
        try:
            subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", ref, "--filter=blob:none", "--sparse",
                            "https://github.com/godotengine/godot.git", str(dest)], capture_output=True, timeout=240)
            subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", "/doc/classes/*.xml",
                            "/modules/*/doc_classes/*.xml"], capture_output=True, timeout=240)
        except (OSError, subprocess.SubprocessError):
            pass
    if not any(dest.rglob("*.xml")):
        import urllib.request
        for rel in ("doc/classes/ProjectSettings.xml", "modules/gdscript/doc_classes/@GDScript.xml"):
            try:
                data = urllib.request.urlopen(f"https://raw.githubusercontent.com/godotengine/godot/{ref}/{rel}", timeout=20).read()
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                (dest / rel).write_bytes(data)
            except Exception:
                pass
    return sorted(dest.rglob("*.xml"))


def merge_doctool(exe, tmp, idx):
    """Property defaults (engine --doctool) + descriptions, ProjectSettings, @GDScript and
    deprecated/experimental flags (official XML of the same tag)."""
    doc = tmp / "doc"
    doc.mkdir(exist_ok=True)
    subprocess.run([exe, "--headless", "--doctool", str(doc)], cwd=str(tmp), capture_output=True, timeout=300)
    official = fetch_official_docs(idx, tmp / "official")
    idx["official_docs"] = bool(official)
    for xf in [*doc.rglob("*.xml"), *official]:  # official last = wins
        try:
            root = ET.parse(xf).getroot()
        except ET.ParseError:
            continue
        name = root.get("name")
        if name == "@GDScript":
            g = idx["classes"].setdefault(name, {
                "kind": "global", "inherits": None, "brief": "GDScript-only built-in functions, annotations and constants.",
                "desc": "", "signals": {}, "enums": {}, "properties": {}, "constants": {}, "methods": {}, "annotations": {}})
            for c in root.iter("constant"):
                g["constants"][c.get("name")] = {"name": c.get("name"), "value": c.get("value"), "description": (c.text or "").strip()}
            for m in root.iter("method"):
                g["methods"][m.get("name")] = _xml_method(m)
            for a in root.iter("annotation"):
                g["annotations"][a.get("name")] = _xml_method(a)
            continue
        cls = idx["classes"].get(name)
        if not cls:
            continue
        for flag in ("deprecated", "experimental"):
            if root.get(flag) is not None:
                cls[flag] = root.get(flag) or True
        for m in root.iter("member"):
            n = m.get("name")
            if n not in cls["properties"]:  # ProjectSettings keys, import options of ResourceImporter*, ...
                cls["properties"][n] = {"name": n, "type": m.get("type")}
            p = cls["properties"].get(n)
            if p is None:
                continue
            if m.get("default") is not None:
                p["default"] = m.get("default")
            if (m.text or "").strip():
                p["description"] = m.text.strip()
            _flags(m, p)
        for tag_, table in (("method", "methods"), ("signal", "signals"), ("constant", "constants")):
            for el in root.iter(tag_):
                entry = cls.get(table, {}).get(el.get("name"))
                if entry is not None:
                    _flags(el, entry)


def _flags(el, entry):
    for flag in ("deprecated", "experimental"):
        if el.get(flag) is not None:
            entry[flag] = el.get(flag) or True


def _xml_method(m):
    ret = m.find("return")
    args = [{"name": a.get("name"), "type": a.get("type"), **({"default_value": a.get("default")} if a.get("default") else {})}
            for a in m.findall("param")]
    d = m.find("description")
    return {"name": m.get("name"), "arguments": args, "return_value": {"type": ret.get("type") if ret is not None else "void"},
            "is_vararg": m.get("qualifiers") == "vararg", "description": (d.text or "").strip() if d is not None else ""}


def _dump(exe, tmp):
    subprocess.run([exe, "--headless", "--dump-extension-api-with-docs"], cwd=str(tmp),
                   capture_output=True, timeout=300)
    if not (tmp / "extension_api.json").is_file():
        emit({"ok": False, "error": "API dump failed (needs Godot 4.3+ with --dump-extension-api-with-docs)"}, 1)


def load_index(rebuild=False):
    exe = godot_or_exit()
    ver = re.sub(r"[^A-Za-z0-9._-]", "_", version(exe) or "unknown")
    path = cache_dir() / ver / "api_index.json"
    if path.is_file() and not rebuild:
        return json.loads(path.read_text("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return build_index(exe, path)


def resolve_class(idx, name):
    if name in idx["classes"]:
        return name
    k = key(name)
    for c in idx["classes"]:
        if key(c) == k:
            return c
    return None


CS_RENAMED = {"Object": "GodotObject", "Thread": "GodotThread", "Array": "Collections.Array",
              "Dictionary": "Collections.Dictionary", "String": "string (+ StringExtensions)",
              "StringName": "StringName", "bool": "bool", "int": "long (int in most APIs)", "float": "double (float in most APIs)",
              "PackedByteArray": "byte[]", "PackedInt32Array": "int[]", "PackedInt64Array": "long[]",
              "PackedFloat32Array": "float[]", "PackedFloat64Array": "double[]", "PackedStringArray": "string[]",
              "PackedVector2Array": "Vector2[]", "PackedVector3Array": "Vector3[]", "PackedVector4Array": "Vector4[]",
              "PackedColorArray": "Color[]", "Nil": "null"}
CS_POOL = {"String": "StringExtensions", "Array": "Collections.Array", "Dictionary": "Collections.Dictionary"}


def cs_class(idx, cls):
    if cls == "@GlobalScope":
        return "GD / Mathf"
    if cls in CS_RENAMED:
        return CS_RENAMED[cls]
    k = key(cls)
    for c in idx["cs"]:
        if "." not in c and key(c) == k:
            return c
    return None


def cs_members(idx, cls, member, kind):
    """C# signatures for a GDScript member (P/M/E/F), matched by normalized name."""
    csc = CS_POOL.get(cls) or cs_class(idx, cls)
    pools = [csc] if csc and cls != "@GlobalScope" else ["GD", "Mathf"]
    if cls.startswith("Packed"):
        return ["C# array: use LINQ / System.Array / Godot extension methods"]
    want = key(member)
    out = []
    for pool in pools:
        for k, n, args in idx["cs"].get(pool, []):
            if kind == "E" and k == "E" and key(n) == want:
                out.append(f"event {n}")
            elif kind in ("M", "P") and k in ("M", "P") and key(n) == want:
                sig = f"({', '.join(cs_type(a) for a in split_args(args or ''))})" if k == "M" else ""
                out.append(f"{pool}.{n}{sig}")
    if kind == "F":
        for sub, mem in idx["cs"].items():
            if csc and sub.startswith(csc + ".") and sub.count(".") == 1:
                for k, n, _ in mem:
                    if k == "F" and want.endswith(key(n)) and key(n):
                        out.append(f"{sub}.{n}")
    return sorted(set(out))[:6]


def prop_type(idx, cls, p):
    """Property type; enum-typed ints resolved through the setter's argument type."""
    t = p.get("type", "")
    if t == "int" and p.get("setter"):
        for c in [cls, *chain(idx, cls)]:
            m = idx["classes"].get(c, {}).get("methods", {}).get(p["setter"])
            if m:
                args = m.get("arguments", [])
                if args:
                    t = args[-1]["type"]
                break
    t = re.sub(r"\d+/\d+:", "", t.replace("enum::", "").replace("bitfield::", "flags "))
    return ",".join(x for x in t.split(",") if not x.startswith("-"))


def chain(idx, cls):
    out, c = [], idx["classes"].get(cls, {}).get("inherits")
    while c:
        out.append(c)
        c = idx["classes"].get(c, {}).get("inherits")
    return out


def find_member(idx, cls, member):
    tables = (("method", "methods"), ("property", "properties"), ("signal", "signals"),
              ("enum", "enums"), ("constant", "constants"), ("annotation", "annotations"))
    if member.endswith("Enum"):  # C# enum names (Node.ProcessModeEnum) -> search enums first
        tables = (("enum", "enums"),) + tuple(t for t in tables if t[0] != "enum")
    for exact in (True, False):  # exact names first (enum Scaling3DMode vs property scaling_3d_mode)
        for c in [cls, *chain(idx, cls)]:
            info = idx["classes"].get(c, {})
            for kind, table in tables:
                t = info.get(table, {})
                if exact and member in t:
                    return c, kind, t[member]
                if not exact:
                    for n in t:  # C# / case-insensitive name
                        if key(n) == key(member) or key(n) == key(member.removesuffix("Enum")):
                            return c, kind, t[n]
            for en, e in info.get("enums", {}).items():
                for v in e.get("values", []):
                    if v["name"] == member or (not exact and key(v["name"]) == key(member)):
                        return c, "enum_value", {"enum": en, **v}
    return None, None, None


def describe_member(idx, cls, member, full, lang):
    owner, kind, m = find_member(idx, cls, member)
    if not owner:
        sugg = [f"{cls}.{n}" for c in [cls, *chain(idx, cls)] for t in ("methods", "properties", "signals")
                for n in idx["classes"].get(c, {}).get(t, {}) if key(member)[:4] in key(n)][:12]
        emit({"ok": False, "error": f"{cls} has no member {member}", "did_you_mean": sugg}, 1)
    name = m["name"]
    res = {"ok": True, "class": owner, "kind": kind, "name": name}
    if owner != cls:
        res["inherited_by"] = cls
    if kind == "annotation":
        res["gd"] = gd_sig(name, m).replace(" -> void", "")
    elif kind == "method":
        res["gd"] = gd_sig(name, m)
        res["cs"] = cs_members(idx, owner, name, "M")
    elif kind == "property":
        res["gd"] = f"{name}: {prop_type(idx, owner, m)}" + (f" = {m['default']}" if m.get("default") is not None else "")             + (f"  (set {m['setter']}/get {m['getter']})" if m.get("setter") else "")
        res["cs"] = cs_members(idx, owner, name, "P")
    elif kind == "signal":
        res["gd"] = gd_sig(name, m, "signal")
        res["cs"] = cs_members(idx, owner, name, "E")
    elif kind == "enum":
        res["values"] = {v["name"]: v["value"] for v in m["values"]}
        res["bitfield"] = m.get("is_bitfield", False)
    elif kind in ("constant", "enum_value"):
        res["value"] = m.get("value")
        if kind == "enum_value":
            res["enum"] = m["enum"]
        res["cs"] = cs_members(idx, owner, name, "F")
    res["desc"] = plain(m.get("description", ""), full, lang)
    for flag in ("deprecated", "experimental"):
        if m.get(flag):
            res[flag] = plain(m[flag]) if isinstance(m[flag], str) else True
    if idx["classes"].get(owner, {}).get("deprecated"):
        res["class_deprecated"] = plain(str(idx["classes"][owner]["deprecated"]))
    return res


def describe_class(idx, cls, full, lang):
    c = idx["classes"][cls]
    res = {"ok": True, "class": cls, "kind": c["kind"], "cs": cs_class(idx, cls), "inherits": chain(idx, cls),
           "brief": plain(c["brief"])}
    for flag in ("deprecated", "experimental"):
        if c.get(flag):
            res[flag] = plain(c[flag]) if isinstance(c[flag], str) else True
    if c.get("singleton"):
        res["singleton"] = True
    if c.get("instantiable") is False:
        res["instantiable"] = False
    if c.get("api_type") == "editor":
        res["editor_only"] = True
    if full:
        res["desc"] = plain(c["desc"], True, lang)
    if c.get("constructors"):
        res["constructors"] = c["constructors"]
    if c.get("annotations"):
        res["annotations"] = list(c["annotations"])
    if cls == "ProjectSettings":
        res["settings_count"] = len([p for p in c["properties"] if "/" in p])
        res["hint"] = "query ProjectSettings.<section/key> or --search <word>"
    res["properties"] = [f"{n}: {prop_type(idx, cls, p)}" for n, p in c["properties"].items() if "/" not in n]
    if cls != "ProjectSettings":  # import options etc. ("meshes/generate_lods")
        res["options"] = [f"{n}: {p.get('type')} = {p.get('default')}" for n, p in c["properties"].items() if "/" in n]
    accessors = {p.get(k) for p in c["properties"].values() for k in ("setter", "getter")}
    res["methods"] = [n + ("*" if m.get("is_virtual") else "") + (" (deprecated)" if m.get("deprecated") else "")
                      for n, m in c["methods"].items() if n not in accessors]
    dep = [n for n, p in c["properties"].items() if p.get("deprecated") and "/" not in n]
    if dep:
        res["deprecated_properties"] = dep
    res["signals"] = list(c["signals"])
    res["enums"] = {n: [v["name"] for v in e["values"]] for n, e in c["enums"].items()}
    if len(c["constants"]) <= 30:
        res["constants"] = list(c["constants"])
    else:
        res["constants_count"] = len(c["constants"])
    res["note"] = "* = virtual. Property accessors and parent members omitted; query Class.member for signatures."
    return {k: v for k, v in res.items() if v not in ([], {}, None, "")}


def search(idx, term, limit):
    rx = re.compile(term, re.I) if any(ch in term for ch in "^$*+?[]()|\\") else None
    low = term.lower()
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", term).lower()  # C# PascalCase -> snake_case
    hits = []
    for cn, c in idx["classes"].items():
        if (rx.search(cn) if rx else low in cn.lower()):
            hits.append(cn)
        for t in ("methods", "properties", "signals", "annotations"):
            for n in c.get(t, {}):
                nl = n.lower()
                if (rx.search(n) if rx else (low in nl or snake in nl)):
                    hits.append(f"{cn}.{n}")
    return {"ok": True, "query": term, "count": len(hits), "hits": hits[:limit]}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    full, lang, rebuild, limit, q = "--full" in argv, "gd", "--rebuild" in argv, 40, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--lang":
            lang, i = argv[i + 1], i + 1
        elif a == "--limit":
            limit, i = int(argv[i + 1]), i + 1
        elif not a.startswith("--") or a == "--search":
            q.append(a)
        i += 1
    idx = load_index(rebuild)
    if q and q[0] == "--search":
        emit(search(idx, q[1], limit))
        return 0
    query = q[0] if q else ""
    if not query:
        emit({"ok": True, "version": idx["version"], "classes": len(idx["classes"])})
        return 0
    cls_name, _, member = query.partition(".")
    cls = resolve_class(idx, cls_name)
    if not member and cls_name[:1].islower():  # lowercase bare name: function before class (range vs Range)
        for scope in ("@GlobalScope", "@GDScript"):
            if cls_name in idx["classes"].get(scope, {}).get("methods", {}):
                emit(describe_member(idx, scope, cls_name, full, lang))
                return 0
    if query.startswith("@") and query not in idx["classes"] and "." not in query:
        cls_name, member = "@GDScript", query
        cls = "@GDScript"
    if not cls and not member:  # bare utility function, GDScript builtin, or global enum/constant
        for scope in ("@GlobalScope", "@GDScript"):
            owner, kind, _ = find_member(idx, scope, cls_name)
            if owner:
                emit(describe_member(idx, scope, cls_name, full, lang))
                return 0
    if not cls:
        emit({"ok": False, "error": f"unknown class {cls_name}", "did_you_mean": search(idx, cls_name, 10)["hits"]}, 1)
    emit(describe_member(idx, cls, member, full, lang) if member else describe_class(idx, cls, full, lang))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
