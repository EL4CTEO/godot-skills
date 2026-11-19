# Godot Agent Skills

Godot **4.7** skills for AI coding agents (Claude Code, Codex, OpenCode, Gemini CLI, GitHub Copilot, Cursor). They cover GDScript and C#/.NET equally.

There are 18 compact skills. Agents look up exact APIs from **your installed engine** instead of guessing, edit scenes safely through Godot itself, and check their work with real compile, test and export runs. Every code example in the skills is compiled on Godot 4.7.2 by the test suite.

## Install

**Claude Code** (plugin):
```
/plugin marketplace add EL4CTEO/godot-skills
/plugin install godot-agent-skills@godot-agent-skills
```

**Any agent** (clone, then run the installer):
```bash
git clone https://github.com/EL4CTEO/godot-skills
./godot-skills/install/install.sh          # macOS / Linux
.\godot-skills\install\install.ps1         # Windows
```
The default installs into `~/.claude/skills` and `~/.agents/skills`. `.agents/skills` is read by Codex, OpenCode, Gemini CLI, Copilot and Cursor. Options: `--agent claude|codex|opencode|gemini|copilot|cursor|all`, `--project DIR` for a single project, `--uninstall`.

**Requirements:** Godot 4.7+ (standard or .NET) and Python 3.9+. For C#, the .NET 8+ SDK. If Godot isn't found automatically, set `GODOT_EXE`.

## Skills

| Skill | What it does |
|---|---|
| `godot-core` | Start here: API lookup, headless runs, scene editing, what's new |
| `godot-gdscript` | Typed GDScript, signals, await, compile check |
| `godot-csharp` | .NET setup, signals, interop, build errors |
| `godot-architecture` | Project structure, autoloads, Resources, saves |
| `godot-2d` | TileMapLayer, Parallax2D, cameras, pixel art |
| `godot-3d-rendering` | Renderers, lighting, GI, materials, import |
| `godot-physics` | Jolt, character controllers, raycasts, ragdolls |
| `godot-ui` | Menus, themes, gamepad focus, localization |
| `godot-input` | Rebinding, gamepads, gyro, touch |
| `godot-animation` | AnimationTree, Tweens, root motion, IK |
| `godot-shaders-vfx` | Shaders, particles, post effects, shader check |
| `godot-audio` | Buses, 3D sound, adaptive music |
| `godot-networking` | Multiplayer, RPCs, replication, HTTP |
| `godot-performance` | Profiling, MultiMesh, threads |
| `godot-export-ci` | Exports, signing, GitHub Actions |
| `godot-editor-tooling` | Tool scripts, editor plugins, importers |
| `godot-testing-debug` | GdUnit4, gdUnit4Net, debugging |
| `godot-xr` | OpenXR VR/AR |

## Try it

> "Add a player with coyote-time jumping and a camera that shakes on landing."
> "My C# build fails after upgrading to 4.7, fix it."
> "Make a main menu that works with a gamepad, then export for Windows and Android."

## Development

```bash
python tools/validate_skills.py --strict   # spec, token budgets, links
python tools/trigger_check.py              # skill routing
python tools/run_tests.py                  # real-engine tests (set GODOT_EXE if needed)
```
