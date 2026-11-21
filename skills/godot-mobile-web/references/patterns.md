# Mobile and Web patterns (compiled by the tests)

## Safe-area MarginContainer (notches, rounded corners, home indicator)
```gdscript
extends MarginContainer

## Wrap the HUD in this. Pads each side by the unsafe area, converted to viewport units.

@export var extra_margin := 8


func _ready() -> void:
	get_viewport().size_changed.connect(_apply)
	_apply()


func _apply() -> void:
	var screen_size := Vector2(DisplayServer.screen_get_size())
	var safe := Rect2(DisplayServer.get_display_safe_area())
	if safe.size.x <= 0.0 or screen_size.x <= 0.0:
		return
	var view := get_viewport().get_visible_rect().size
	var to_view := view / screen_size  # stretch mode makes viewport units differ from pixels
	var left := safe.position.x * to_view.x
	var top := safe.position.y * to_view.y
	var right := (screen_size.x - safe.end.x) * to_view.x
	var bottom := (screen_size.y - safe.end.y) * to_view.y
	add_theme_constant_override("margin_left", int(left) + extra_margin)
	add_theme_constant_override("margin_top", int(top) + extra_margin)
	add_theme_constant_override("margin_right", int(right) + extra_margin)
	add_theme_constant_override("margin_bottom", int(bottom) + extra_margin)
```

## App lifecycle and Android back button (autoload)
```gdscript
extends Node

## Autoload "AppLifecycle". Saves on pause, routes the back button to menus.

signal back_requested
signal paused_by_os

var save_callback: Callable


func _ready() -> void:
	get_tree().quit_on_go_back = false  # we decide when back quits
	process_mode = Node.PROCESS_MODE_ALWAYS


func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT:
			if save_callback.is_valid():
				save_callback.call()  # iOS gives ~5 s before killing a paused app
			get_tree().paused = true
			paused_by_os.emit()
		NOTIFICATION_WM_GO_BACK_REQUEST:
			back_requested.emit()


func quit_from_main_menu() -> void:
	get_tree().quit()
```
```csharp
using Godot;

public partial class AppLifecycle : Node
{
    [Signal] public delegate void BackRequestedEventHandler();

    public System.Action? Save { get; set; }

    public override void _Ready()
    {
        GetTree().QuitOnGoBack = false;
        ProcessMode = ProcessModeEnum.Always;
    }

    public override void _Notification(int what)
    {
        if (what == NotificationApplicationPaused || what == NotificationApplicationFocusOut)
        {
            Save?.Invoke();
            GetTree().Paused = true;
        }
        else if (what == NotificationWMGoBackRequest)
        {
            EmitSignal(SignalName.BackRequested);
        }
    }
}
```

## Touch camera: one-finger pan, two-finger pinch zoom (2D)
```gdscript
extends Camera2D

@export var min_zoom := 0.5
@export var max_zoom := 3.0

var _touches: Dictionary[int, Vector2] = {}
var _start_distance := 0.0
var _start_zoom := Vector2.ONE


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:
			_touches[event.index] = event.position
		else:
			_touches.erase(event.index)
		if _touches.size() == 2:
			_start_distance = _distance()
			_start_zoom = zoom
	elif event is InputEventScreenDrag:
		_touches[event.index] = event.position
		if _touches.size() == 1:
			position -= event.relative / zoom
		elif _touches.size() == 2 and _start_distance > 0.0:
			var factor := _distance() / _start_distance
			zoom = (_start_zoom * factor).clampf(min_zoom, max_zoom)


func _distance() -> float:
	var points := _touches.values()
	return (points[0] as Vector2).distance_to(points[1] as Vector2)
```

## Haptic feedback helper (phone + gamepad, respects a setting)
```gdscript
extends Node

## Autoload "Haptics".

var enabled := true


func pulse(strength := 0.5, duration_ms := 40) -> void:
	if not enabled:
		return
	if OS.has_feature("mobile") or OS.has_feature("web_android"):
		Input.vibrate_handheld(duration_ms, strength)  # Android needs permissions/vibrate
	for pad in Input.get_connected_joypads():
		Input.start_joy_vibration(pad, strength, strength * 0.5, duration_ms / 1000.0)
```

## One store API on every platform (wraps native plugins)
```gdscript
extends Node

## Autoload "Store". Game code only talks to this; platform plugins are optional singletons.

signal purchased(product_id: String)
signal failed(product_id: String, reason: String)

const ANDROID_SINGLETON := "GodotGooglePlayBilling"
const IOS_SINGLETON := "InAppStore"

var _backend: Object


func _ready() -> void:
	for singleton_name in [ANDROID_SINGLETON, IOS_SINGLETON]:
		if Engine.has_singleton(singleton_name):
			_backend = Engine.get_singleton(singleton_name)
			break


func is_available() -> bool:
	return _backend != null or OS.is_debug_build()


func buy(product_id: String) -> void:
	if _backend == null:
		if OS.is_debug_build():
			purchased.emit.call_deferred(product_id)  # fake success in editor/desktop debug
		else:
			failed.emit.call_deferred(product_id, "store unavailable")
		return
	# Call the plugin's own purchase method here, then emit purchased/failed from its callbacks.
	# Validate receipts on your server before granting anything valuable.
	failed.emit.call_deferred(product_id, "not wired for %s" % OS.get_name())
```

## Web: JavaScript bridge, file download, audio unlock
```gdscript
extends Node

var _on_visibility: JavaScriptObject  # keep a reference or the callback is garbage collected


func _ready() -> void:
	if not OS.has_feature("web"):
		return
	var document := JavaScriptBridge.get_interface("document")
	_on_visibility = JavaScriptBridge.create_callback(_visibility_changed)
	document.addEventListener("visibilitychange", _on_visibility)


func _visibility_changed(_args: Array) -> void:
	var hidden: bool = JavaScriptBridge.eval("document.hidden", true)
	get_tree().paused = hidden


func export_save(data: Dictionary) -> void:
	var bytes := JSON.stringify(data, "\t").to_utf8_buffer()
	if OS.has_feature("web"):
		JavaScriptBridge.download_buffer(bytes, "save.json", "application/json")
	else:
		var f := FileAccess.open("user://save_export.json", FileAccess.WRITE)
		f.store_buffer(bytes)


func local_storage_set(key: String, value: String) -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.get_interface("localStorage").setItem(key, value)
```
```gdscript
extends Control

## "Tap to start" screen: browsers only start audio after a user gesture.

@export_file("*.tscn") var next_scene := ""


func _gui_input(event: InputEvent) -> void:
	var tapped: bool = (event is InputEventMouseButton and event.pressed) or (event is InputEventScreenTouch and event.pressed)
	if tapped or event.is_action_pressed("ui_accept"):
		accept_event()
		get_tree().change_scene_to_file(next_scene)
```

## Runtime permission request (Android)
```gdscript
extends Node

signal microphone_ready(granted: bool)


func request_microphone() -> void:
	if not OS.has_feature("android"):
		microphone_ready.emit(true)
		return
	if "android.permission.RECORD_AUDIO" in OS.get_granted_permissions():
		microphone_ready.emit(true)
		return
	get_tree().on_request_permissions_result.connect(_on_result, CONNECT_ONE_SHOT)
	OS.request_permission("android.permission.RECORD_AUDIO")


func _on_result(permission: String, granted: bool) -> void:
	if permission == "android.permission.RECORD_AUDIO":
		microphone_ready.emit(granted)
```
