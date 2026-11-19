# XR patterns (compiled by the test suite)

## XR startup: init check, refresh rate, physics sync, session lifecycle
```gdscript
extends Node3D

signal focus_lost
signal focus_gained

@export var preferred_refresh_rate := 90.0

var xr: OpenXRInterface


func _ready() -> void:
	xr = XRServer.find_interface("OpenXR") as OpenXRInterface
	if xr == null or not xr.is_initialized():
		push_warning("OpenXR not initialized: running flat (enable xr/openxr/enabled, connect a headset)")
		return
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)  # the headset paces frames
	get_viewport().use_xr = true
	xr.session_begun.connect(_on_session_begun)
	xr.session_focussed.connect(func() -> void: focus_gained.emit())
	xr.session_visible.connect(func() -> void: focus_lost.emit())  # visible but not focused = system menu
	xr.session_stopping.connect(func() -> void: get_tree().quit())
	xr.pose_recentered.connect(func() -> void: XRServer.center_on_hmd(XRServer.RESET_BUT_KEEP_TILT, true))


func _on_session_begun() -> void:
	var rates := xr.get_available_display_refresh_rates()
	if preferred_refresh_rate in rates:
		xr.display_refresh_rate = preferred_refresh_rate
	var hz := xr.display_refresh_rate if xr.display_refresh_rate > 0.0 else 72.0
	Engine.physics_ticks_per_second = int(round(hz))  # held objects follow hands without jitter
	xr.foveation_level = 2
	xr.foveation_dynamic = true
```

## Controller input, snap turn, haptics
```gdscript
extends XROrigin3D

@export var snap_angle_degrees := 30.0
@export var move_speed := 2.0

@onready var left: XRController3D = $LeftHand
@onready var right: XRController3D = $RightHand
@onready var camera: XRCamera3D = $XRCamera3D

var _turn_ready := true


func _ready() -> void:
	right.button_pressed.connect(func(action: String) -> void:
		if action == "trigger_click":
			right.trigger_haptic_pulse(&"haptic", 0.0, 0.5, 0.1, 0.0))


func _physics_process(delta: float) -> void:
	var turn := right.get_vector2(&"primary").x
	if absf(turn) > 0.7 and _turn_ready:
		_turn_ready = false
		_rotate_around_camera(-signf(turn) * deg_to_rad(snap_angle_degrees))
	elif absf(turn) < 0.3:
		_turn_ready = true
	var stick := left.get_vector2(&"primary")
	if stick.length() > 0.15:
		var fwd := -camera.global_basis.z
		fwd.y = 0.0
		var side := camera.global_basis.x
		side.y = 0.0
		global_position += (fwd.normalized() * stick.y + side.normalized() * stick.x) * move_speed * delta


func _rotate_around_camera(angle: float) -> void:
	var pivot := camera.global_position
	var t := global_transform
	t.origin -= pivot
	t = t.rotated(Vector3.UP, angle)
	t.origin += pivot
	global_transform = t
```

## Passthrough (mixed reality) via environment blend mode
```gdscript
extends Node

@export var world_environment: WorldEnvironment


func set_passthrough(enabled: bool) -> bool:
	var xr := XRServer.find_interface("OpenXR")
	if xr == null or not xr.is_initialized():
		return false
	if enabled and XRInterface.XR_ENV_BLEND_MODE_ALPHA_BLEND not in xr.get_supported_environment_blend_modes():
		return false
	xr.environment_blend_mode = XRInterface.XR_ENV_BLEND_MODE_ALPHA_BLEND if enabled else XRInterface.XR_ENV_BLEND_MODE_OPAQUE
	get_viewport().transparent_bg = enabled
	if world_environment and world_environment.environment:
		var env := world_environment.environment
		env.background_mode = Environment.BG_COLOR if enabled else Environment.BG_SKY
		env.background_color = Color(0, 0, 0, 0)
	return true
```

## C#: XR bootstrap
```csharp
using Godot;

public partial class XrBootstrap : Node3D
{
    public override void _Ready()
    {
        var xr = XRServer.FindInterface("OpenXR") as OpenXRInterface;
        if (xr is null || !xr.IsInitialized())
        {
            GD.PushWarning("OpenXR not initialized; running flat.");
            return;
        }
        DisplayServer.WindowSetVsyncMode(DisplayServer.VSyncMode.Disabled);
        GetViewport().UseXR = true;
        xr.SessionBegun += () => Engine.PhysicsTicksPerSecond = (int)Mathf.Round(xr.DisplayRefreshRate > 0 ? xr.DisplayRefreshRate : 72f);
    }
}
```
