#!/usr/bin/env python3
"""Heuristic trigger check: do Godot skill descriptions win for prompts they should own?

Scores each prompt against every description (token overlap, IDF weighted) and checks that the
expected skill is in the top 2. A cheap regression guard when editing descriptions; real agents
use richer matching.
Usage: python tools/trigger_check.py
"""
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = [
    ("what is the exact signature of look_at in Godot 4.7 and its C# name", "godot-core"),
    ("run the game headless and tell me which errors appear", "godot-core"),
    ("fix this GDScript parse error and add static types to my script", "godot-gdscript"),
    ("my C# Godot project fails to build, csproj and partial class errors", "godot-csharp"),
    ("how should I structure folders, autoloads and a save system for my game", "godot-architecture"),
    ("make a tilemap with terrains and parallax background for a 2D platformer", "godot-2d"),
    ("set up lighting with SDFGI, AgX tonemapping and an area light in my 3D scene", "godot-3d-rendering"),
    ("character controller with move_and_slide, slopes, Jolt and raycasts", "godot-physics"),
    ("build a main menu with containers, themes and gamepad focus navigation", "godot-ui"),
    ("let players rebind keys and support gamepad gyro aiming", "godot-input"),
    ("blend walk and run with an AnimationTree blend space and add leg IK", "godot-animation"),
    ("write a dissolve shader and a particle explosion effect", "godot-shaders-vfx"),
    ("adaptive music that switches to combat, audio buses and 3D sound", "godot-audio"),
    ("online multiplayer with ENet, RPCs and MultiplayerSynchronizer", "godot-networking"),
    ("the game stutters, profile and optimize thousands of enemies with MultiMesh", "godot-performance"),
    ("export to Android and Windows and set up GitHub Actions CI", "godot-export-ci"),
    ("write an editor plugin with a custom dock and an import plugin", "godot-editor-tooling"),
    ("write unit tests with GdUnit4 and debug a crash", "godot-testing-debug"),
    ("make a VR game with OpenXR controllers and passthrough", "godot-xr"),
    ("C# signals are not disconnecting and I get ObjectDisposedException", "godot-csharp"),
    ("pixel art camera smoothing and y-sort for a top-down game", "godot-2d"),
    ("localize the UI and add screen reader accessibility", "godot-ui"),
    ("enemies should pathfind on the navmesh, avoid each other and chase the player", "godot-navigation-ai"),
    ("behavior tree or utility AI for my NPCs, with AStarGrid2D for the tactics grid", "godot-navigation-ai"),
    ("third-person orbit camera with SpringArm3D and a GridMap level", "godot-3d-gameplay"),
    ("generate random dungeons and caves with noise and a seed", "godot-procedural"),
    ("upgrade my Godot 3 project and port code from Unity", "godot-migration"),
    ("handle the notch safe area, Android back button and web export threads hosting", "godot-mobile-web"),
    ("branching dialogue with choices, a typewriter text box and a quest log", "godot-narrative"),
    ("let players install mods as PCK packs and sell DLC", "godot-modding-dlc"),
    ("add screen shake, hit-stop and juice so attacks feel impactful", "godot-game-feel"),
    ("which addon should I install from the Asset Store and is this GDExtension compatible", "godot-addons"),
]


def toks(s):
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2]


def main():
    descs = {}
    for md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        m = re.search(r"^description: (.*)$", md.read_text("utf-8"), re.M)
        descs[md.parent.name] = set(toks(m.group(1)) + toks(md.parent.name))
    n = len(descs)
    idf = {}
    for d in descs.values():
        for t in d:
            idf[t] = idf.get(t, 0) + 1
    idf = {t: math.log(n / c) + 0.1 for t, c in idf.items()}
    fails = 0
    for prompt, want in CASES:
        q = set(toks(prompt))
        ranked = sorted(descs, key=lambda k: -sum(idf.get(t, 0) for t in q & descs[k]))
        ok = want in ranked[:2]
        fails += not ok
        print(f"{'ok ' if ok else 'MISS'} {want:<30} top: {ranked[0]}, {ranked[1]}  <- {prompt}")
    print(f"{len(CASES) - fails}/{len(CASES)} in top-2")
    return 1 if fails > len(CASES) // 10 else 0


if __name__ == "__main__":
    sys.exit(main())
