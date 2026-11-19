# 2D patterns (compiled by the test suite)

## Platformer controller: coyote time, jump buffer, variable jump height
```gdscript
extends CharacterBody2D

@export var speed := 180.0
@export var acceleration := 1400.0
@export var friction := 1600.0
@export var jump_velocity := -380.0
@export var coyote_time := 0.1
@export var jump_buffer := 0.12
@export_range(0.0, 1.0) var jump_cut := 0.45

var gravity: float = ProjectSettings.get_setting("physics/2d/default_gravity")
var _coyote := 0.0
var _buffer := 0.0


func _physics_process(delta: float) -> void:
	_coyote = coyote_time if is_on_floor() else maxf(_coyote - delta, 0.0)
	_buffer = jump_buffer if Input.is_action_just_pressed("jump") else maxf(_buffer - delta, 0.0)

	if not is_on_floor():
		velocity.y += gravity * delta
	if _buffer > 0.0 and _coyote > 0.0:
		velocity.y = jump_velocity
		_buffer = 0.0
		_coyote = 0.0
	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= jump_cut

	var dir := Input.get_axis("move_left", "move_right")
	if dir != 0.0:
		velocity.x = move_toward(velocity.x, dir * speed, acceleration * delta)
	else:
		velocity.x = move_toward(velocity.x, 0.0, friction * delta)
	move_and_slide()
```

## Top-down 8-way movement (analog-friendly)
```gdscript
extends CharacterBody2D

@export var max_speed := 200.0
@export var accel := 12.0


func _ready() -> void:
	motion_mode = MOTION_MODE_FLOATING


func _physics_process(delta: float) -> void:
	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = velocity.lerp(input * max_speed, 1.0 - exp(-accel * delta))  # frame-rate independent
	move_and_slide()
```

## Camera shake with decaying noise (offset, not position)
```gdscript
extends Camera2D

@export var max_offset := Vector2(12, 8)
@export var decay := 1.8

var trauma := 0.0
var _noise := FastNoiseLite.new()
var _t := 0.0


func add_trauma(amount: float) -> void:
	trauma = minf(trauma + amount, 1.0)


func _process(delta: float) -> void:
	trauma = maxf(trauma - decay * delta, 0.0)
	_t += delta * 60.0
	var shake := trauma * trauma
	offset = Vector2(max_offset.x * shake * _noise.get_noise_1d(_t),
			max_offset.y * shake * _noise.get_noise_1d(_t + 1000.0))
```

## TileMapLayer queries: world position to cell, custom data, terrain painting
```gdscript
extends Node2D

@onready var ground: TileMapLayer = $Ground


func is_hazard_at(world_pos: Vector2) -> bool:
	var cell := ground.local_to_map(ground.to_local(world_pos))
	var data := ground.get_cell_tile_data(cell)
	return data != null and data.get_custom_data("is_hazard")


func dig(world_pos: Vector2) -> void:
	ground.erase_cell(ground.local_to_map(ground.to_local(world_pos)))


func paint_room(rect: Rect2i, terrain_set: int, terrain: int) -> void:
	var cells: Array[Vector2i] = []
	for x in range(rect.position.x, rect.end.x):
		for y in range(rect.position.y, rect.end.y):
			cells.append(Vector2i(x, y))
	ground.set_cells_terrain_connect(cells, terrain_set, terrain)
```
```csharp
using Godot;

public partial class TileQueries : Node2D
{
    private TileMapLayer _ground = null!;

    public override void _Ready() => _ground = GetNode<TileMapLayer>("Ground");

    public bool IsHazardAt(Vector2 worldPos)
    {
        Vector2I cell = _ground.LocalToMap(_ground.ToLocal(worldPos));
        TileData? data = _ground.GetCellTileData(cell);
        return data is not null && data.GetCustomData("is_hazard").AsBool();
    }
}
```

## Custom drawing (redraw only when data changes)
```gdscript
@tool
extends Node2D

@export var radius := 48.0:
	set(value):
		radius = value
		queue_redraw()
@export var color := Color(0.3, 0.8, 1.0)


func _draw() -> void:
	draw_circle(Vector2.ZERO, radius, Color(color, 0.25))
	draw_arc(Vector2.ZERO, radius, 0.0, TAU, 64, color, 2.0, true)
	draw_ellipse(Vector2(0, radius + 8), radius * 0.6, 6.0, Color(0, 0, 0, 0.3))  # 4.7+
```
