# Godot Agent Skills: agent instructions

This repo contains Agent Skills (`skills/<name>/SKILL.md`, agentskills.io format) for **Godot 4.7** (standard and .NET builds, GDScript and C#). Codex, OpenCode, Gemini CLI, Copilot and Cursor read them from `.agents/skills`, and Claude Code reads `.claude/skills` (see `install/`).

## Using the skills
- Start any Godot task with `skills/godot-core/SKILL.md`. It routes to the right skill and defines the verification loop.
- **Never guess an API:** `python skills/godot-core/scripts/api_lookup.py Class.member` reads the installed engine and returns GDScript and C# signatures, defaults and deprecations.
- Run scripts; don't read them. Every `skills/*/scripts/*.py` documents its flags in its docstring and prints one compact JSON result. Set `GODOT_EXE` if the engine isn't found.
- Load a skill's `references/*.md` only when the SKILL.md points you there.
- Verify edits: `gd_check.py` (GDScript), `cs_build.py` (C#), `shader_check.py` (shaders), `run_godot.py smoke`, `test_run.py`. Project checks: `migrate_scan.py` (stale APIs), `addon_inspect.py` (addons), `serve_web.py --check` (Web exports).

| Skill | Use for |
|---|---|
| godot-core | API lookup, headless runs, scene editing, project facts, 4.5–4.7 changes (start here) |
| godot-gdscript | typed GDScript, signals and await, patterns, compile check |
| godot-csharp | .NET setup, partial classes, signals, marshaling, interop, build errors |
| godot-architecture | folders, composition, autoloads, Resources, state machines, saves |
| godot-2d | TileMapLayer, Parallax2D, Camera2D, pixel art, 2D lights |
| godot-3d-rendering | renderers, Environment, lights (AreaLight3D), GI, materials, import, HDR |
| godot-physics | Jolt, CharacterBody, RigidBody, Areas, queries, ragdolls |
| godot-ui | Controls, containers, themes, focus navigation, localization, accessibility |
| godot-input | actions, rebinding, gamepads, gyro, touch, VirtualJoystick |
| godot-animation | AnimationPlayer/Tree, Tween, root motion, IK framework |
| godot-shaders-vfx | shading language, stencil, particles, compositor, shader check |
| godot-audio | buses, 3D audio, adaptive music |
| godot-networking | multiplayer, RPC, replication, HTTP |
| godot-performance | profiling, MultiMesh, servers, threads |
| godot-export-ci | presets, templates, signing, platforms, GitHub Actions |
| godot-editor-tooling | @tool, EditorPlugin/EditorDock, importers, GDExtension |
| godot-testing-debug | GdUnit4, gdUnit4Net, debugging, Logger |
| godot-xr | OpenXR, controllers, passthrough, comfort |
| godot-navigation-ai | navmesh, agents, avoidance, AStarGrid2D, enemy AI, behavior trees |
| godot-3d-gameplay | third-person/orbit/RTS cameras, GridMap, CSG, interactables |
| godot-procedural | seeded RNG, noise, caves/dungeons, heightmap meshes, chunks |
| godot-migration | Godot 3 → 4.7, 4.x → 4.7, Unity concepts, stale-API scanner |
| godot-mobile-web | safe area, lifecycle, touch, IAP, Web threads/hosting, web server |
| godot-narrative | dialogue addons vs custom, typewriter boxes, quests, cutscenes |
| godot-modding-dlc | PCK mods, manifests, load order, runtime assets, DLC, patches |
| godot-game-feel | screen shake, hit-stop, flashes, tweens, Movie Maker |
| godot-addons | Asset Store, vetting, GDExtension checks, curated 4.7 list |

## Working on this repo
- Shared helper: edit `shared/_godotx.py` only, then run `python tools/sync_shared.py`.
- Validate: `python tools/validate_skills.py --strict` (spec, token budgets, links, script contract). `python tools/trigger_check.py` checks routing.
- Test: `python tools/run_tests.py [filter]` needs Godot 4.7 (.NET build plus the .NET 8+ SDK for C# tests; set `GODOT_EXE`). Every ```gdscript, ```csharp and ```gdshader block in the skills is compiled on the real engine. Keep blocks complete and compilable.
- Keep each SKILL.md under ~2.5k tokens and each description under 400 characters. Verify every API claim with `api_lookup.py` against 4.7 before writing it.
