# Input patterns (compiled by the test suite)

## Rebinding with persistence (ConfigFile stores InputEvent resources safely as values)
```gdscript
extends Node

const PATH := "user://input.cfg"
const REBINDABLE: Array[StringName] = [&"move_left", &"move_right", &"move_up", &"move_down", &"jump"]


func _ready() -> void:
	load_bindings()


func rebind(action: StringName, event: InputEvent, slot_is_gamepad: bool) -> void:
	for old in InputMap.action_get_events(action):
		var old_is_pad := old is InputEventJoypadButton or old is InputEventJoypadMotion
		if old_is_pad == slot_is_gamepad:
			InputMap.action_erase_event(action, old)
	InputMap.action_add_event(action, event)
	save_bindings()


func save_bindings() -> void:
	var cfg := ConfigFile.new()
	for action in REBINDABLE:
		cfg.set_value("bindings", action, InputMap.action_get_events(action))
	cfg.save(PATH)


func load_bindings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	for action in REBINDABLE:
		var events: Array = cfg.get_value("bindings", action, [])
		if events.is_empty():
			continue
		InputMap.action_erase_events(action)
		for ev in events:
			if ev is InputEvent:
				InputMap.action_add_event(action, ev)


func reset_to_defaults() -> void:
	InputMap.load_from_project_settings()
	DirAccess.remove_absolute(PATH)
```

## "Press a key" capture for a rebind button
```gdscript
extends Button

signal captured(event: InputEvent)

@export var gamepad := false

var _listening := false


func _ready() -> void:
	pressed.connect(func() -> void:
		_listening = true
		text = "Press %s..." % ("a button" if gamepad else "a key"))


func _input(event: InputEvent) -> void:
	if not _listening or not event.is_pressed() or event.is_echo():
		return
	var ok := (event is InputEventJoypadButton) if gamepad else (event is InputEventKey or event is InputEventMouseButton)
	if event is InputEventJoypadMotion and gamepad and absf(event.axis_value) > 0.6:
		var motion := event as InputEventJoypadMotion
		motion.axis_value = signf(motion.axis_value)
		ok = true
	if ok:
		_listening = false
		text = event.as_text()
		captured.emit(event)
		get_viewport().set_input_as_handled()
```

## Last-used device detection for button prompts
```gdscript
extends Node

signal device_changed(kind: StringName)

var kind: StringName = &"keyboard"


func _input(event: InputEvent) -> void:
	var next := kind
	if event is InputEventJoypadButton or (event is InputEventJoypadMotion and absf(event.axis_value) > 0.3):
		var pad_name := Input.get_joy_name(event.device).to_lower()
		next = &"playstation" if pad_name.contains("dualsense") or pad_name.contains("ps") else &"xbox"
	elif event is InputEventKey or event is InputEventMouseButton:
		next = &"keyboard"
	elif event is InputEventScreenTouch:
		next = &"touch"
	if next != kind:
		kind = next
		device_changed.emit(kind)
```

## Gyro aiming (4.7 motion sensors) blended with the right stick
```gdscript
extends Node3D

@export var device := 0
@export var gyro_sensitivity := 1.0
@export var stick_speed := 3.0

@onready var pivot: Node3D = $CameraPivot


func _ready() -> void:
	if Input.has_joy_motion_sensors(device):
		Input.set_joy_motion_sensors_enabled(device, true)


func _process(delta: float) -> void:
	var look := Vector2(Input.get_joy_axis(device, JOY_AXIS_RIGHT_X), Input.get_joy_axis(device, JOY_AXIS_RIGHT_Y))
	if look.length() < 0.15:
		look = Vector2.ZERO
	rotate_y(-look.x * stick_speed * delta)
	pivot.rotate_x(-look.y * stick_speed * delta)
	if Input.is_joy_motion_sensors_enabled(device):
		var gyro := Input.get_joy_gyroscope(device)  # rad/s: x pitch, y yaw, z roll
		rotate_y(gyro.y * gyro_sensitivity * delta)
		pivot.rotate_x(gyro.x * gyro_sensitivity * delta)
	pivot.rotation.x = clampf(pivot.rotation.x, -1.4, 1.4)
```

## Touch camera: one-finger drag to orbit, pinch to zoom
```gdscript
extends Camera3D

@export var orbit_speed := 0.005
@export var zoom_speed := 0.01

var _touches: Dictionary[int, Vector2] = {}
var _last_pinch := 0.0


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:
			_touches[event.index] = event.position
		else:
			_touches.erase(event.index)
		_last_pinch = 0.0
	elif event is InputEventScreenDrag:
		_touches[event.index] = event.position
		if _touches.size() == 1:
			get_parent().rotate_y(-event.relative.x * orbit_speed)
		elif _touches.size() == 2:
			var points := _touches.values()
			var dist: float = (points[0] as Vector2).distance_to(points[1])
			if _last_pinch > 0.0:
				position.z = clampf(position.z - (dist - _last_pinch) * zoom_speed, 2.0, 30.0)
			_last_pinch = dist
```

## C#: cached actions, device filtering for local multiplayer
```csharp
using Godot;

public partial class PlayerInput : Node
{
    private static readonly StringName Jump = "jump";
    [Export] public int Device { get; set; }

    [Signal] public delegate void JumpPressedEventHandler();

    public Vector2 Move => new(
        Input.GetJoyAxis(Device, JoyAxis.LeftX), Input.GetJoyAxis(Device, JoyAxis.LeftY));

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event.Device != Device || @event is not InputEventJoypadButton)
            return;
        if (@event.IsActionPressed(Jump))
            EmitSignal(SignalName.JumpPressed);
    }
}
```
