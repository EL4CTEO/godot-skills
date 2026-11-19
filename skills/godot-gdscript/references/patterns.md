# GDScript patterns (each block is a complete script, compiled by the test suite on 4.7)

## Typed component with signals, setter, exports and doc comments
```gdscript
class_name Stamina
extends Node
## Regenerating resource. Emits [signal changed] on every change.

signal changed(current: float, maximum: float)
signal depleted

@export_range(1.0, 500.0, 1.0, "or_greater") var maximum := 100.0
@export var regen_per_second := 15.0
@export_group("Advanced")
@export var regen_delay := 0.75

var current: float = maximum:
	set(value):
		var clamped := clampf(value, 0.0, maximum)
		if is_equal_approx(clamped, current):
			return
		current = clamped
		changed.emit(current, maximum)
		if current == 0.0:
			depleted.emit()

var _cooldown := 0.0


func _physics_process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown -= delta
	else:
		current += regen_per_second * delta


## Returns false (and spends nothing) when there is not enough stamina.
func try_spend(amount: float) -> bool:
	if amount > current:
		return false
	current -= amount
	_cooldown = regen_delay
	return true
```

## Abstract base, variadic args, static members, typed collections (4.5+)
```gdscript
@abstract
class_name Weapon
extends Node3D

static var shots_fired_total := 0

@export var damage := 10
var _hits: Dictionary[StringName, int] = {}


@abstract func _fire_projectile(direction: Vector3) -> void


func fire(direction: Vector3) -> void:
	shots_fired_total += 1
	_fire_projectile(direction.normalized())


func register_hit(target: StringName) -> void:
	_hits[target] = _hits.get(target, 0) + 1


static func describe(...parts: Array) -> String:
	return " | ".join(parts.map(func(p: Variant) -> String: return str(p)))
```

## await, timers, tweens and safe coroutines
```gdscript
extends Node2D

signal intro_finished

@onready var _sprite: Sprite2D = $Sprite2D


func play_intro() -> void:
	var tween := create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(_sprite, "modulate:a", 1.0, 0.4).from(0.0)
	tween.parallel().tween_property(_sprite, "scale", Vector2.ONE, 0.4).from(Vector2(0.6, 0.6))
	await tween.finished
	await get_tree().create_timer(0.25).timeout
	if not is_inside_tree():  # the node may have been freed or removed meanwhile
		return
	intro_finished.emit()


func load_level_async(path: String) -> PackedScene:
	ResourceLoader.load_threaded_request(path)
	while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
	return ResourceLoader.load_threaded_get(path) as PackedScene
```

## Signals: bind, one-shot, lambdas, autoload bus
```gdscript
extends Control

@onready var _grid: GridContainer = %Grid


func _ready() -> void:
	for i in 9:
		var b := Button.new()
		b.text = str(i + 1)
		b.pressed.connect(_on_slot_pressed.bind(i))
		_grid.add_child(b)
	Events.player_died.connect(_on_player_died, CONNECT_ONE_SHOT)
	Events.score_changed.connect(func(new_score: int) -> void: print("score ", new_score))


func _on_slot_pressed(index: int) -> void:
	print("slot ", index)


func _on_player_died() -> void:
	get_tree().reload_current_scene.call_deferred()
```

## match with guards and destructuring
```gdscript
extends RefCounted


func classify(value: Variant) -> String:
	match value:
		0:
			return "zero"
		var n when n is int and n < 0:
			return "negative"
		[var x, var y]:
			return "pair %s,%s" % [x, y]
		{"type": "enemy", "hp": var hp}:
			return "enemy with %d hp" % hp
		_:
			return "other"
```

## Inner classes, enums and constants as data
```gdscript
extends Node

enum State { IDLE, RUN, JUMP }

const SPEEDS: Dictionary[State, float] = {State.IDLE: 0.0, State.RUN: 6.0, State.JUMP: 4.0}

var state := State.IDLE


class Snapshot:
	var position: Vector3
	var state: int

	func _init(p_position: Vector3, p_state: int) -> void:
		position = p_position
		state = p_state


func snapshot(at: Vector3) -> Snapshot:
	return Snapshot.new(at, state)
```

## Tool script with an inspector button (4.4+)
```gdscript
@tool
extends Node3D

@export_tool_button("Scatter", "Add") var scatter_action := _scatter
@export var count := 10


func _scatter() -> void:
	for child in get_children():
		child.queue_free()
	for i in count:
		var marker := Marker3D.new()
		marker.position = Vector3(randf_range(-5, 5), 0, randf_range(-5, 5))
		add_child(marker)
		marker.owner = get_tree().edited_scene_root  # makes it saved with the scene
```
