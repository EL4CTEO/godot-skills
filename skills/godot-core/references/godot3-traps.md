# Stale-knowledge traps (Godot 3 / early 4.x → 4.7)

Every name on the right exists in 4.7.2. Confirm anything not listed here with `api_lookup.py`. C# names are the PascalCase forms (`move_and_slide` → `MoveAndSlide`), with a few renames: `Object`→`GodotObject`, `Thread`→`GodotThread`, `Array`→`Godot.Collections.Array`, and acronyms (`GPUParticles2D`→`GpuParticles2D`, `HTTPRequest`→`HttpRequest`).

## Syntax (GDScript)
| Old | 4.7 |
|---|---|
| `export var x = 1`, `onready var`, `tool` | `@export var x := 1`, `@onready var`, `@tool` |
| `setget set_x, get_x` | `var x: int: set = set_x, get = get_x` or an inline `set(v):` block |
| `yield(obj, "sig")`, `yield(get_tree().create_timer(1), "timeout")` | `await obj.sig`, `await get_tree().create_timer(1.0).timeout` |
| `connect("sig", obj, "method", [binds])` | `sig.connect(obj.method.bind(...))` |
| `emit_signal("sig", a)` | `sig.emit(a)` (`emit_signal` still exists but is untyped) |
| `funcref(obj, "m")` | `obj.m` (a `Callable`), or `Callable(obj, "m")` |
| `remote`/`master`/`puppet` keywords | `@rpc("any_peer", "call_local", "reliable")` |
| `PoolStringArray` and others | `PackedStringArray`, `PackedVector3Array`, … |
| `.empty()` | `.is_empty()` |
| `instance()` | `instantiate()` |
| `deg2rad`, `rand_range`, `stepify`, `range_lerp` | `deg_to_rad`, `randf_range`, `snapped`, `remap` |
| `str2var`, `to_json`, `parse_json` | `str_to_var`, `JSON.stringify`, `JSON.parse_string` |
| `Array.invert()`, `find_last` | `reverse()`, `rfind` |
| Untyped dictionaries only | Typed `Dictionary[String, int]` (4.4+) |
| `Engine.editor_hint` | `Engine.is_editor_hint()` |

## Nodes and classes
| Old | 4.7 |
|---|---|
| `KinematicBody(2D)` + `move_and_slide(vel, up)` | `CharacterBody3D/2D`: set `velocity` and `up_direction`, then call `move_and_slide()` with no arguments |
| `Spatial`, `Position3D/2D`, `Listener` | `Node3D`, `Marker3D/2D`, `AudioListener3D` |
| `Sprite`, `AnimatedSprite`, `Light2D` | `Sprite2D`, `AnimatedSprite2D`, `PointLight2D` |
| `MeshInstance`, `Camera`, `RayCast`, `Particles` | add a `3D` suffix: `MeshInstance3D`, `Camera3D`, `RayCast3D`, `GPUParticles3D` |
| `TileMap` (deprecated) | one `TileMapLayer` node per layer |
| `ParallaxBackground`/`ParallaxLayer` (deprecated) | `Parallax2D` |
| `YSort` | `y_sort_enabled` on any `CanvasItem` |
| `Tween` node | `create_tween()` (a RefCounted that starts on its own) |
| `ViewportContainer` + `Viewport` | `SubViewportContainer` + `SubViewport` |
| `GIProbe`, `BakedLightmap` | `VoxelGI`, `LightmapGI` (or SDFGI on the Environment) |
| `VisibilityNotifier` | `VisibleOnScreenNotifier3D/2D` |
| `ImmediateGeometry` | `ImmediateMesh` |
| `Navigation` node | `NavigationRegion3D` + `NavigationAgent3D` (+ `NavigationServer3D`) |
| `SkeletonIK3D` (deprecated) | IK framework (4.6+): `TwoBoneIK3D`, `FABRIK3D`, `CCDIK3D`, `SplineIK3D`, `JacobianIK3D` |
| `ARVROrigin`, `ARVRServer` | `XROrigin3D`, `XRServer` |
| `VisualServer`, `Physics2DServer` | `RenderingServer`, `PhysicsServer2D` |
| `Reference` | `RefCounted` |
| `StreamTexture` | `CompressedTexture2D` |
| `NetworkedMultiplayerENet`, `get_tree().network_peer` | `ENetMultiplayerPeer`, `multiplayer.multiplayer_peer` |
| `is_network_master()` | `is_multiplayer_authority()` |

## Members and APIs
| Old | 4.7 |
|---|---|
| `translation` (Spatial), `rect_position`, `rect_min_size`, `margin_*` | `position`, `position`, `custom_minimum_size`, `offset_*` |
| `update()` on CanvasItem | `queue_redraw()` |
| `get_tree().change_scene(path)` | `change_scene_to_file(path)`, `change_scene_to_packed(ps)`, `change_scene_to_node(node)` (4.7) |
| `File.new().open()`, `Directory` | `FileAccess.open(path, FileAccess.READ)`, `DirAccess.open()` (static) |
| `OS.get_ticks_msec()`, `OS.get_datetime()` | `Time.get_ticks_msec()`, `Time.get_datetime_dict_from_system()` |
| `OS.window_size`, `OS.window_fullscreen` | `get_window().size`, `DisplayServer.window_set_mode(...)` |
| `InputEventKey.scancode`, `BUTTON_LEFT` | `keycode`/`physical_keycode`, `MOUSE_BUTTON_LEFT` |
| `AnimationPlayer.playback_speed` | `speed_scale` |
| `RigidBody.mode = MODE_STATIC/KINEMATIC` | `freeze = true` + `freeze_mode` |
| `add_central_force` (continuous), `applied_force` | `apply_central_force` (per frame) or `constant_force` |
| `contacts_reported` | `max_contacts_reported` (+ `contact_monitor = true`) |
| `is_a_parent_of` | `is_ancestor_of` |
| `.tscn` with `format=2` | `format=3`. Scenes saved in 4.6+ carry `unique_id=` on nodes, and `load_steps` is gone |

## 4.x changes old 4.x code still trips on
- `Resource.duplicate(true)` no longer deep-copies external sub-resources (4.5). Use `duplicate_deep()`.
- `Node.get_rpc_config` became `get_node_rpc_config` (4.5).
- `StreamPeerTCP.poll/get_status` and `TCPServer.is_connection_available/stop` moved to their base classes `StreamPeerSocket`/`SocketServer` (4.6). GDScript calls still work, but C# binaries must be rebuilt.
- `AnimationPlayer.current_animation`/`assigned_animation`/`autoplay` became `StringName` (4.6). This breaks C# code.
- BlendSpace1D/2D `sync` (bool) became `sync_mode` (enum) (4.7).
- `RichTextLabel.add_image(..., width_in_percent)` became a `width_unit: ImageUnit` argument (4.7).
- In 4.7, a GDScript override of a method with a typed return must itself return on every path (`return null` where needed).
- In 4.7, keyboard and mouse events report `InputEvent.DEVICE_ID_KEYBOARD`/`DEVICE_ID_MOUSE` instead of `0`.
