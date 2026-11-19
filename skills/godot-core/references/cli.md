# Godot 4.7 command line (verified against 4.7.2 `--help`)

Always pass `--headless` for automated runs. It implies the dummy display and audio drivers, and nothing renders.
On Windows use the `*_console.exe` build so stdout and the exit code reach your shell.

| Goal | Command |
|---|---|
| Version | `godot --version` → `4.7.2.stable.mono.official.<hash>` |
| Import assets, build `.godot/` caches | `godot --headless --path P --import` |
| Run main scene for N frames | `godot --headless --path P --quit-after 120` |
| Run a given scene | `godot --path P res://levels/l1.tscn` (or `--scene uid://…`) |
| Run a tool script | `godot --headless --path P -s res://tools/x.gd -- user args` (script `extends SceneTree` or `MainLoop`) |
| Parse-check one script | `godot --headless --path P --check-only -s res://a.gd` (exit code 1 on errors) |
| Build C# solution | `godot --headless --path P --build-solutions --quit` (or plain `dotnet build`) |
| Export | `--export-release "<preset>" out/game.exe`, `--export-debug`, `--export-pack` (.pck/.zip), `--export-patch` (+ `--patches a.pck,b.pck`) |
| Android build template | `--install-android-build-template` together with `--export-*` |
| API dump | `--dump-extension-api[-with-docs]`, `--doctool <dir>`, `--gdscript-docs res://src` |
| Debug visuals while running | `--debug-collisions`, `--debug-paths`, `--debug-navigation`, `--debug-avoidance` |
| Local stdout debugger / breakpoints | `-d`, `-b res://p.gd:12,res://q.gd:40` |
| Remote debug to an editor | `--remote-debug tcp://127.0.0.1:6007` |
| Deterministic capture | `--fixed-fps 60 --write-movie out.avi --quit-after 600` |
| Profiling and timing | `--profiling`, `--gpu-profile`, `--benchmark`, `--print-fps` |
| Force renderer or driver | `--rendering-method forward_plus/mobile/gl_compatibility`, `--rendering-driver vulkan/d3d12/metal/opengl3` |
| GDScript LSP/DAP for IDEs | `--lsp-port 6005`, `--dap-port 6006` (with `-e`) |
| Editor recovery | `--recovery-mode` |
| Godot 3 project conversion | `--convert-3to4` (dry run: `--validate-conversion-3to4`) |

Read user args (after `--`) with `OS.get_cmdline_user_args()`.
To quit from a `SceneTree` script, call `quit(exit_code)`. A `MainLoop` script returns `true` from `_process()`. Use `MainLoop` when autoloads must not run.
