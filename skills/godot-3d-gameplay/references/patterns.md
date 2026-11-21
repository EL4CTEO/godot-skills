# 3D gameplay patterns (compiled by the tests)

## Third-person controller (camera-relative, model faces movement)
```gdscript
extends CharacterBody3D

@export var speed := 6.0
@export var acceleration := 30.0
@export var friction := 20.0
@export var jump_velocity := 5.0
@export var turn_speed := 12.0

@onready var model: Node3D = $Model
@onready var rig: Node3D = $CameraRig


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	elif Input.is_action_just_pressed("jump"):
		velocity.y = jump_velocity

	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var yaw := Basis(Vector3.UP, rig.global_rotation.y)  # yaw only: pitch must not slow movement
	var dir := (yaw * Vector3(input.x, 0.0, input.y)).normalized()
	var planar := Vector2(velocity.x, velocity.z)
	if dir:
		planar = planar.move_toward(Vector2(dir.x, dir.z) * speed, acceleration * delta)
		var target_yaw := atan2(-dir.x, -dir.z)
		model.rotation.y = lerp_angle(model.rotation.y, target_yaw, turn_speed * delta)
	else:
		planar = planar.move_toward(Vector2.ZERO, friction * delta)
	velocity.x = planar.x
	velocity.z = planar.y
	move_and_slide()
```

## Orbit camera rig (top_level, SpringArm3D, mouse + stick)
```gdscript
extends Node3D

## CameraRig (top_level = true) > Pitch > SpringArm3D > Camera3D

@export var target: Node3D
@export var height := 1.5
@export var follow_speed := 12.0
@export var mouse_sensitivity := 0.003
@export var stick_speed := 3.0
@export var min_pitch := -70.0
@export var max_pitch := 50.0

@onready var pitch: Node3D = $Pitch
@onready var arm: SpringArm3D = $Pitch/SpringArm3D


func _ready() -> void:
	top_level = true
	if target is CollisionObject3D:
		arm.add_excluded_object((target as CollisionObject3D).get_rid())
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_look(event.relative * mouse_sensitivity)


func _process(delta: float) -> void:
	var stick := Input.get_vector("look_left", "look_right", "look_up", "look_down")
	if stick:
		_look(stick * stick_speed * delta)
	if target:
		var goal := target.get_global_transform_interpolated().origin + Vector3.UP * height
		global_position = global_position.lerp(goal, 1.0 - exp(-follow_speed * delta))


func _look(amount: Vector2) -> void:
	rotation.y -= amount.x
	pitch.rotation.x = clampf(pitch.rotation.x - amount.y, deg_to_rad(min_pitch), deg_to_rad(max_pitch))
```
```csharp
using Godot;

public partial class OrbitRig : Node3D
{
    [Export] public Node3D? Target { get; set; }
    [Export] public float Height { get; set; } = 1.5f;
    [Export] public float FollowSpeed { get; set; } = 12f;
    [Export] public float MouseSensitivity { get; set; } = 0.003f;

    private Node3D _pitch = null!;

    public override void _Ready()
    {
        TopLevel = true;
        _pitch = GetNode<Node3D>("Pitch");
        if (Target is CollisionObject3D body)
            GetNode<SpringArm3D>("Pitch/SpringArm3D").AddExcludedObject(body.GetRid());
        Input.MouseMode = Input.MouseModeEnum.Captured;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is InputEventMouseMotion motion && Input.MouseMode == Input.MouseModeEnum.Captured)
        {
            RotateY(-motion.Relative.X * MouseSensitivity);
            float pitch = _pitch.Rotation.X - motion.Relative.Y * MouseSensitivity;
            _pitch.Rotation = _pitch.Rotation with { X = Mathf.Clamp(pitch, Mathf.DegToRad(-70f), Mathf.DegToRad(50f)) };
        }
    }

    public override void _Process(double delta)
    {
        if (Target is null)
            return;
        Vector3 goal = Target.GetGlobalTransformInterpolated().Origin + Vector3.Up * Height;
        GlobalPosition = GlobalPosition.Lerp(goal, 1f - Mathf.Exp(-FollowSpeed * (float)delta));
    }
}
```

## Lock-on targeting
```gdscript
extends Node3D

## Put on the camera rig. Cycles the nearest visible enemy in front of the camera.

signal lock_changed(target: Node3D)

@export var max_distance := 20.0
@export var camera: Camera3D

var locked: Node3D


func toggle_lock() -> void:
	locked = null if locked else _best_target()
	lock_changed.emit(locked)


func _best_target() -> Node3D:
	var best: Node3D = null
	var best_score := INF
	var center := get_viewport().get_visible_rect().size * 0.5
	for node in get_tree().get_nodes_in_group(&"lockable"):
		var enemy := node as Node3D
		if enemy == null or camera.is_position_behind(enemy.global_position):
			continue
		var dist := camera.global_position.distance_to(enemy.global_position)
		if dist > max_distance:
			continue
		var score := camera.unproject_position(enemy.global_position).distance_to(center) + dist * 10.0
		if score < best_score:
			best_score = score
			best = enemy
	return best


func _process(delta: float) -> void:
	if locked == null or not is_instance_valid(locked):
		return
	var to_target := locked.global_position - global_position
	var yaw := atan2(-to_target.x, -to_target.z)
	rotation.y = lerp_angle(rotation.y, yaw, 1.0 - exp(-10.0 * delta))
```

## Top-down aim at the mouse on the ground plane
```gdscript
extends CharacterBody3D

@onready var camera: Camera3D = get_viewport().get_camera_3d()
@onready var model: Node3D = $Model


func _process(_delta: float) -> void:
	var mouse := get_viewport().get_mouse_position()
	var ground := Plane(Vector3.UP, global_position.y)
	var hit: Variant = ground.intersects_ray(camera.project_ray_origin(mouse), camera.project_ray_normal(mouse))
	if hit != null:
		var aim: Vector3 = hit
		aim.y = model.global_position.y
		if model.global_position.distance_squared_to(aim) > 0.01:
			model.look_at(aim)
```

## RTS camera (pan, edge scroll, zoom, bounds)
```gdscript
extends Node3D

@export var pan_speed := 20.0
@export var edge_margin := 12.0
@export var zoom_step := 2.0
@export var min_height := 6.0
@export var max_height := 40.0
@export var bounds := Rect2(-100, -100, 200, 200)

@onready var camera: Camera3D = $Camera3D


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera.position.y = maxf(camera.position.y - zoom_step, min_height)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera.position.y = minf(camera.position.y + zoom_step, max_height)


func _process(delta: float) -> void:
	var move := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var mouse := get_viewport().get_mouse_position()
	var size := get_viewport().get_visible_rect().size
	if mouse.x < edge_margin: move.x = -1.0
	elif mouse.x > size.x - edge_margin: move.x = 1.0
	if mouse.y < edge_margin: move.y = -1.0
	elif mouse.y > size.y - edge_margin: move.y = 1.0
	var dir := Basis(Vector3.UP, rotation.y) * Vector3(move.x, 0.0, move.y)
	position += dir * pan_speed * delta * (camera.position.y / min_height)
	position.x = clampf(position.x, bounds.position.x, bounds.end.x)
	position.z = clampf(position.z, bounds.position.y, bounds.end.y)
```

## GridMap painting from code (level editor, procedural rooms)
```gdscript
extends GridMap

const FLOOR := 0
const WALL := 1


func build_room(origin: Vector3i, size: Vector2i) -> void:
	for x in size.x:
		for z in size.y:
			var cell := origin + Vector3i(x, 0, z)
			set_cell_item(cell, FLOOR)
			var edge := x == 0 or z == 0 or x == size.x - 1 or z == size.y - 1
			if edge:
				var facing := Basis(Vector3.UP, PI * 0.5) if x == 0 or x == size.x - 1 else Basis()
				set_cell_item(cell + Vector3i.UP, WALL, get_orthogonal_index_from_basis(facing))


func cell_under(world_pos: Vector3) -> Vector3i:
	return local_to_map(to_local(world_pos))


func item_name_at(cell: Vector3i) -> String:
	var item := get_cell_item(cell)
	return "" if item == INVALID_CELL_ITEM else mesh_library.get_item_name(item)
```

## Bake a CSG blockout into a static mesh + collider (tool script)
```gdscript
@tool
extends CSGCombiner3D

## Click "bake" in the inspector to replace the CSG with a MeshInstance3D + StaticBody3D sibling.

@export_tool_button("Bake to static mesh") var bake := _bake


func _bake() -> void:
	var mesh := bake_static_mesh()
	var shape := bake_collision_shape()
	if mesh == null or mesh.get_surface_count() == 0:
		push_warning("CSG produced no geometry")
		return
	var mi := MeshInstance3D.new()
	mi.name = name + "_Baked"
	mi.mesh = mesh
	var body := StaticBody3D.new()
	var col := CollisionShape3D.new()
	col.shape = shape
	body.add_child(col)
	mi.add_child(body)
	get_parent().add_child(mi)
	mi.transform = transform
	for n: Node in [mi, body, col]:
		n.owner = get_tree().edited_scene_root
	visible = false
```

## Rail camera / moving platform along a Path3D
```gdscript
extends PathFollow3D

@export var duration := 8.0
@export var ping_pong := true


func _ready() -> void:
	loop = not ping_pong
	var tween := create_tween().set_loops().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)  # AnimatableBody3D children carry riders
	tween.tween_property(self, "progress_ratio", 1.0, duration).from(0.0)
	if ping_pong:
		tween.tween_property(self, "progress_ratio", 0.0, duration)
```

## Health bars over 3D enemies (2D UI following 3D points)
```gdscript
extends Control

## A HUD layer that keeps a ProgressBar over every node in group "show_health".

@export var bar_scene: PackedScene
@export var offset := Vector3(0, 2.2, 0)

var _bars := {}


func _process(_delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	for node in get_tree().get_nodes_in_group(&"show_health"):
		var enemy := node as Node3D
		var bar: ProgressBar = _bars.get(enemy)
		if bar == null:
			bar = bar_scene.instantiate()
			add_child(bar)
			_bars[enemy] = bar
			enemy.tree_exiting.connect(func() -> void:
				bar.queue_free()
				_bars.erase(enemy))
		var world := enemy.global_position + offset
		bar.visible = not camera.is_position_behind(world)
		bar.position = camera.unproject_position(world) - bar.size * 0.5
		bar.value = enemy.get(&"health") if &"health" in enemy else bar.value
```
