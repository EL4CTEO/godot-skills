# Architecture patterns (compiled by the test suite)

## Event bus autoload (register as "Events")
```gdscript
extends Node
## Global signals only: no state, no logic. Emit: Events.coin_collected.emit(5)

signal coin_collected(amount: int)
signal enemy_killed(enemy_id: StringName, position: Vector3)
signal request_scene_change(path: String)
```
```csharp
using Godot;

public partial class EventBus : Node
{
    public static EventBus Instance { get; private set; } = null!;

    [Signal] public delegate void CoinCollectedEventHandler(int amount);
    [Signal] public delegate void EnemyKilledEventHandler(StringName enemyId, Vector3 position);

    public override void _EnterTree() => Instance = this;
}
```

## Enum state machine (small and fast)
```gdscript
extends CharacterBody2D

enum State { IDLE, RUN, JUMP, FALL }

const SPEED := 220.0
const JUMP_VELOCITY := -420.0

var state := State.IDLE
var gravity: float = ProjectSettings.get_setting("physics/2d/default_gravity")


func _physics_process(delta: float) -> void:
	var dir := Input.get_axis("move_left", "move_right")
	match state:
		State.IDLE, State.RUN:
			velocity.x = dir * SPEED
			if Input.is_action_just_pressed("jump"):
				velocity.y = JUMP_VELOCITY
				_set_state(State.JUMP)
			elif not is_on_floor():
				_set_state(State.FALL)
			else:
				_set_state(State.RUN if dir != 0.0 else State.IDLE)
		State.JUMP, State.FALL:
			velocity.x = dir * SPEED
			velocity.y += gravity * delta
			if is_on_floor():
				_set_state(State.IDLE)
			elif velocity.y > 0.0:
				_set_state(State.FALL)
	move_and_slide()


func _set_state(next: State) -> void:
	if next == state:
		return
	state = next  # play animations / sounds on enter here
```

## Node-based state machine (many states with enter/exit)
```gdscript
class_name StateMachine
extends Node

signal state_changed(from: StringName, to: StringName)

@export var initial: MachineState

var current: MachineState


func _ready() -> void:
	for child in get_children():
		if child is MachineState:
			child.machine = self
	current = initial if initial else get_child(0) as MachineState
	current.enter()


func _physics_process(delta: float) -> void:
	current.physics_update(delta)


func transition(to_name: StringName) -> void:
	var next := get_node_or_null(NodePath(to_name)) as MachineState
	if next == null or next == current:
		return
	current.exit()
	state_changed.emit(current.name, next.name)
	current = next
	current.enter()
```
```gdscript
class_name MachineState
extends Node

var machine: StateMachine


func enter() -> void:
	pass


func exit() -> void:
	pass


func physics_update(_delta: float) -> void:
	pass
```

## Save system: versioned JSON in user:// (safe, no code execution)
```gdscript
extends Node

const SAVE_PATH := "user://save_%d.json"
const VERSION := 2


func save_game(slot: int, data: Dictionary) -> Error:
	data["version"] = VERSION
	var file := FileAccess.open(SAVE_PATH % slot, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(data, "\t"))
	return OK


func load_game(slot: int) -> Dictionary:
	if not FileAccess.file_exists(SAVE_PATH % slot):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH % slot))
	if parsed is not Dictionary:
		push_warning("corrupt save slot %d" % slot)
		return {}
	return _migrate(parsed)


func _migrate(data: Dictionary) -> Dictionary:
	if int(data.get("version", 1)) < 2:
		data["coins"] = data.get("gold", 0)  # v1 called it gold
		data.erase("gold")
	data["version"] = VERSION
	return data
```
```csharp
using System.Globalization;
using System.Text.Json;
using Godot;

public partial class SaveSystem : Node
{
    private const string Path = "user://save_{0}.json";

    public sealed record SaveData(int Version, int Coins, string Level, float PlayTime);

    public void Save(int slot, SaveData data)
    {
        using var file = FileAccess.Open(string.Format(CultureInfo.InvariantCulture, Path, slot), FileAccess.ModeFlags.Write);
        file?.StoreString(JsonSerializer.Serialize(data)); // System.Text.Json is culture-invariant
    }

    public SaveData? Load(int slot)
    {
        string p = string.Format(CultureInfo.InvariantCulture, Path, slot);
        return FileAccess.FileExists(p) ? JsonSerializer.Deserialize<SaveData>(FileAccess.GetFileAsString(p)) : null;
    }
}
```

## Settings with ConfigFile
```gdscript
extends Node

const PATH := "user://settings.cfg"

var config := ConfigFile.new()


func _ready() -> void:
	config.load(PATH)  # missing file is fine: defaults below
	AudioServer.set_bus_volume_linear(AudioServer.get_bus_index(&"Master"), config.get_value("audio", "master", 0.8))
	get_window().mode = config.get_value("video", "window_mode", Window.MODE_WINDOWED)


func set_value(section: String, key: String, value: Variant) -> void:
	config.set_value(section, key, value)
	config.save(PATH)
```

## Scene manager with a threaded loading screen
```gdscript
extends CanvasLayer

signal progress(ratio: float)

var _path := ""


func change_scene(path: String) -> void:
	_path = path
	visible = true
	ResourceLoader.load_threaded_request(path, "PackedScene", true)
	set_process(true)


func _process(_delta: float) -> void:
	if _path.is_empty():
		set_process(false)
		return
	var ratio := []
	match ResourceLoader.load_threaded_get_status(_path, ratio):
		ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			progress.emit(ratio[0])
		ResourceLoader.THREAD_LOAD_LOADED:
			get_tree().change_scene_to_packed(ResourceLoader.load_threaded_get(_path))
			_path = ""
			visible = false
		_:
			push_error("failed to load %s" % _path)
			_path = ""
			visible = false
```
