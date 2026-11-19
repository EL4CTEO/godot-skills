# What's new in 4.5, 4.6 and 4.7 (what to use, what changed)

Sources: a diff of the 4.4, 4.5 and 4.7.2 `extension_api.json` files, the official release notes and the migration guides. Check exact signatures with `api_lookup.py`.

## 4.7 (current: 4.7.2, Aug 2026; patch releases have no compatibility breaks)
**Use**
- `AreaLight3D`: a rectangular area light (`area_size`, `area_texture`, `area_normalize_energy`) for screens, windows and neon tubes. Shadows use PCSS. Mobile has an approximate penumbra and Compatibility has no area-light shadows. It costs more GPU time than omni and spot lights.
- HDR output on Windows, macOS, iOS, visionOS and Linux Wayland: `Window.hdr_output_requested`, `DisplayServer.window_is_hdr_output_supported()`.
- `Tween.tween_await(signal)`: pauses a tween until the signal fires. `AwaitTweener.set_timeout()` adds a timeout.
- `VirtualJoystick`: a built-in touch joystick (Fixed, Dynamic and Following modes).
- Gamepad motion sensors: `Input.set_joy_motion_sensors_enabled()`, `get_joy_gyroscope()`, `get_joy_accelerometer()`, `get_joy_gravity()`. Also `has_joy_light()`/`set_joy_light()`, plus vibration queries.
- `Control.offset_transform_*`: a visual transform (position, rotation, scale, pivot) that containers don't overwrite. It's handy for juicy UI animation.
- `SceneTree.change_scene_to_node(node)`; `Thread.is_main_thread()` (C#: `GodotThread.IsMainThread()`).
- `PopupMenu`/`OptionButton` search bar; `RichTextLabel` `[img height=1em]` sizing; conic gradients (`GradientTexture2D.FILL_CONIC`).
- 3D particle scale and rotation: `ParticleProcessMaterial.use_scale_3d`, `use_rotation_3d`.
- `CSGShape3D.autosmooth`/`smoothing_angle`; `Window.set_taskbar_progress_*`; Android picture-in-picture (`DisplayServer.pip_mode_*`).
- `AccessibilityServer` (accessibility moved out of `DisplayServer`); `GodotInstance` (LibGodot embedding).
- Editor: the Asset Store replaces the Asset Library, there's an export template downloader per platform, a MeshLibrary editor and inline shader previews.

**Breaking / behavior**
- New projects default to stretch mode `canvas_items` and aspect `expand`.
- `AnimationNodeBlendSpace1D/2D.sync` became `sync_mode` (enum).
- GDScript: an override of a typed-return method must return explicitly. Setting one element of a packed array no longer calls the property setter.
- `InputEvent.device` is `DEVICE_ID_KEYBOARD`/`DEVICE_ID_MOUSE` for keyboard and mouse.
- Jolt: `WorldBoundaryShape3D.plane.d` sign is flipped. SoftBody3D mass defaults to 1 kg total. `Area3D` now reports SoftBody3D overlaps.
- `AudioStreamPlayer2D/3D.area_mask` default is now 0. `LookAtModifier3D.relative` default is now false.
- CanvasItem line drawing lost its antialiasing feather, so lines look thinner.
- C# binary or source breaks: `Animation.length` is `double`; `Control.accessibility_live` moved to an `AccessibilityServer` enum; `RichTextLabel` image `width_unit`/`height_unit`; `EditorSceneFormatImporter` flags moved to the `ImportFlags` enum.
- macOS 11+ is required. `AudioEffectSpectrumAnalyzer.tap_back_pos` was removed.

## 4.6
**Use**
- **Jolt is the default 3D physics engine for new projects.** Existing projects keep their setting (`physics/3d/physics_engine`).
- New IK framework on `SkeletonModifier3D`: `IKModifier3D` with `TwoBoneIK3D`, `FABRIK3D`, `CCDIK3D`, `SplineIK3D`, `JacobianIK3D`, plus `JointLimitationCone3D`, `BoneTwistDisperser3D` and `LimitAngularVelocityModifier3D`.
- `Control.pivot_offset_ratio` (a 0–1 pivot). Mouse focus and keyboard focus are separate (`grab_focus(hide_focus)`).
- SSR overhaul; glow blends before tonemapping (default blend mode is Screen); `Environment.tonemap_agx_white`/`tonemap_agx_contrast`; octahedral reflection probes.
- Unique node IDs in scenes; delta-encoded patch PCKs (`--export-patch`); Direct3D 12 is the default on Windows for new projects.
- Tracy, Perfetto and Instruments profiling for GDScript, C# and GDExtension.
- `StreamPeerUDS`/`UDSServer` (Unix domain sockets).
- Editor: the Modern theme, floating docks and a select-only mode. `EditorDock` lets plugins create docks.

**Breaking / behavior**
- C#: `AnimationPlayer.current_animation`/`assigned_animation`/`autoplay` are `StringName`.
- `MeshInstance3D.skeleton` default changed to `NodePath("")`.
- Glow defaults changed, and volumetric fog looks brighter.
- `StreamPeerTCP`/`TCPServer` methods moved to `StreamPeerSocket`/`SocketServer`.
- `FileAccess.get_as_text(skip_cr)` lost its argument.
- Re-save scenes through **Project > Tools > Upgrade Project Files** to avoid large VCS diffs.

## 4.5
**Use**
- GDScript `@abstract` classes and methods; variadic functions `func f(...args: Array)`.
- Script backtraces (`Engine.capture_script_backtraces()`, `ScriptBacktrace`). Custom `Logger` subclasses via `OS.add_logger()` for in-game bug reports.
- `duplicate_deep()` on `Array`, `Dictionary` and `Resource`. Plain `duplicate(true)` no longer copies external sub-resources.
- `ResourceUID.path_to_uid()`/`uid_to_path()`.
- Stencil buffer on `BaseMaterial3D` (`stencil_mode`, outline and x-ray presets); bent normals; specular occlusion; SMAA.
- Shader baker (export option) pre-compiles shaders for much faster first loads.
- Screen readers via AccessKit (`Control.accessibility_*`, experimental). `FoldableContainer`.
- `Control.focus_behavior_recursive`/`mouse_behavior_recursive` disable input for a whole subtree.
- TileMapLayer physics chunking (`physics_quadrant_size`, default 16 cells per body).
- Bone constraints: `AimModifier3D`, `CopyTransformModifier3D`, `ConvertTransformModifier3D`.
- SDL3 gamepad driver; a separate 2D navigation server; `Input.is_action_just_pressed_by_event()`.
- `SceneTree.scene_changed` signal; `Node.get_orphan_node_ids()`.

**Breaking / behavior**
- C# Android export needs .NET 9 (the csproj generated by 4.7 adds a `net9.0` condition for Android).
- `Node.get_rpc_config` was renamed `get_node_rpc_config`.
- `TileMapLayer.get_coords_for_body_rid()` behaves differently because of chunking. Set `physics_quadrant_size = 1` to get the old behavior.
- Navigation region updates are asynchronous by default.
