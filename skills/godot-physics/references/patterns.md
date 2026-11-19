# Physics patterns (compiled by the test suite)

## First-person controller (mouse look, gravity from Areas, pushing rigid bodies)
```gdscript
extends CharacterBody3D

@export var speed := 5.0
@export var sprint_speed := 8.0
@export var jump_velocity := 4.5
@export var mouse_sensitivity := 0.002
@export var push_force := 1.5

@onready var head: Node3D = $Head


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * mouse_sensitivity)
		head.rotate_x(-event.relative.y * mouse_sensitivity)
		head.rotation.x = clampf(head.rotation.x, deg_to_rad(-89), deg_to_rad(89))
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	elif Input.is_action_just_pressed("jump"):
		velocity.y = jump_velocity

	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	var dir := (transform.basis * Vector3(input.x, 0, input.y)).normalized()
	var target_speed := sprint_speed if Input.is_physical_key_pressed(KEY_SHIFT) else speed
	velocity.x = move_toward(velocity.x, dir.x * target_speed, target_speed * 10.0 * delta)
	velocity.z = move_toward(velocity.z, dir.z * target_speed, target_speed * 10.0 * delta)
	move_and_slide()

	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var body := c.get_collider() as RigidBody3D
		if body:
			body.apply_central_impulse(-c.get_normal() * push_force)
```

## Raycast query (hitscan) and mouse picking
```gdscript
extends Node3D

@export_flags_3d_physics var hit_mask := 1 | 4


func hitscan(from: Vector3, to: Vector3, exclude: Array[RID] = []) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(from, to, hit_mask, exclude)
	query.collide_with_areas = true
	return get_world_3d().direct_space_state.intersect_ray(query)


func pick_under_mouse(camera: Camera3D, max_distance := 1000.0) -> Node:
	var mouse := get_viewport().get_mouse_position()
	var origin := camera.project_ray_origin(mouse)
	var hit := hitscan(origin, origin + camera.project_ray_normal(mouse) * max_distance)
	return hit.get("collider") as Node
```
```csharp
using Godot;
using Godot.Collections;

public partial class Hitscan : Node3D
{
    [Export(PropertyHint.Layers3DPhysics)] public uint HitMask { get; set; } = 1 | 4;

    public Dictionary Cast(Vector3 from, Vector3 to, Array<Rid>? exclude = null)
    {
        var query = PhysicsRayQueryParameters3D.Create(from, to, HitMask, exclude ?? new Array<Rid>());
        query.CollideWithAreas = true;
        return GetWorld3D().DirectSpaceState.IntersectRay(query);
    }

    public Node? PickUnderMouse(Camera3D camera, float maxDistance = 1000f)
    {
        Vector2 mouse = GetViewport().GetMousePosition();
        Vector3 origin = camera.ProjectRayOrigin(mouse);
        Dictionary hit = Cast(origin, origin + camera.ProjectRayNormal(mouse) * maxDistance);
        return hit.Count > 0 ? hit["collider"].As<Node>() : null;
    }
}
```

## Hitbox / hurtbox with Areas
```gdscript
class_name Hurtbox
extends Area3D

signal hurt(amount: int, from: Node3D)

@export var invulnerable_time := 0.4

var _invulnerable := false


func _ready() -> void:
	area_entered.connect(_on_area_entered)


func _on_area_entered(area: Area3D) -> void:
	if _invulnerable or not area.has_meta(&"damage"):
		return
	hurt.emit(int(area.get_meta(&"damage")), area.owner as Node3D)
	_invulnerable = true
	await get_tree().create_timer(invulnerable_time, false, true).timeout
	_invulnerable = false
```

## Interact prompt with ShapeCast3D
```gdscript
extends ShapeCast3D

signal focus_changed(target: Node)

var focused: Node


func _physics_process(_delta: float) -> void:
	var best: Node = null
	for i in get_collision_count():
		var c := get_collider(i) as Node
		if c and c.has_method(&"interact"):
			best = c
			break
	if best != focused:
		focused = best
		focus_changed.emit(focused)


func try_interact(actor: Node) -> void:
	if focused and is_instance_valid(focused):
		focused.call(&"interact", actor)
```

## Ragdoll on death (PhysicalBoneSimulator3D)
```gdscript
extends Node3D

@onready var simulator: PhysicalBoneSimulator3D = $Armature/Skeleton3D/PhysicalBoneSimulator3D
@onready var anim: AnimationPlayer = $AnimationPlayer


func die(hit_impulse: Vector3, hit_bone: StringName) -> void:
	anim.stop()
	simulator.physical_bones_start_simulation()
	for bone in simulator.get_children():
		if bone is PhysicalBone3D and bone.bone_name == hit_bone:
			bone.apply_central_impulse(hit_impulse)
```

## Teleport a body safely (interpolation-aware)
```gdscript
extends CharacterBody3D


func teleport(to: Transform3D) -> void:
	global_transform = to
	velocity = Vector3.ZERO
	reset_physics_interpolation()  # no smeared frame between old and new position
```
