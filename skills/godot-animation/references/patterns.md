# Animation patterns (compiled by the test suite)

## Drive an AnimationTree from a character (state machine + blend space + one-shot)
```gdscript
extends CharacterBody3D

@onready var anim_tree: AnimationTree = $AnimationTree
@onready var playback: AnimationNodeStateMachinePlayback = anim_tree["parameters/playback"]


func _physics_process(_delta: float) -> void:
	var local_vel := global_transform.basis.inverse() * velocity
	anim_tree["parameters/Locomotion/blend_position"] = Vector2(local_vel.x, -local_vel.z) / 6.0
	anim_tree["parameters/conditions/grounded"] = is_on_floor()
	anim_tree["parameters/conditions/airborne"] = not is_on_floor()
	if not is_on_floor() and playback.get_current_node() != &"Fall":
		playback.travel(&"Fall")


func attack() -> void:
	anim_tree["parameters/Attack/request"] = AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE


func is_attacking() -> bool:
	return anim_tree["parameters/Attack/active"]
```
```csharp
using Godot;

public partial class CharacterAnimator : Node
{
    private static readonly StringName BlendPath = "parameters/Locomotion/blend_position";
    private static readonly StringName AttackRequest = "parameters/Attack/request";

    [Export] public AnimationTree Tree { get; set; } = null!;
    private AnimationNodeStateMachinePlayback _playback = null!;

    public override void _Ready() =>
        _playback = Tree.Get("parameters/playback").As<AnimationNodeStateMachinePlayback>();

    public void UpdateLocomotion(Vector2 normalizedVelocity) => Tree.Set(BlendPath, normalizedVelocity);

    public void Attack() => Tree.Set(AttackRequest, (int)AnimationNodeOneShot.OneShotRequest.Fire);

    public void Travel(StringName state) => _playback.Travel(state);
}
```

## Root motion applied to a CharacterBody3D
```gdscript
extends CharacterBody3D

@onready var anim_tree: AnimationTree = $AnimationTree


func _ready() -> void:
	anim_tree.root_motion_track = ^"Armature/Skeleton3D:Root"
	anim_tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS


func _physics_process(delta: float) -> void:
	var motion := anim_tree.get_root_motion_position()
	quaternion = quaternion * anim_tree.get_root_motion_rotation()
	var horizontal := (global_basis * motion) / delta
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	if not is_on_floor():
		velocity += get_gravity() * delta
	move_and_slide()
```

## Leg IK with TwoBoneIK3D (4.6+), set up from code
```gdscript
extends Skeleton3D

@export var left_foot_target: Node3D
@export var left_knee_pole: Node3D


func _ready() -> void:
	var ik := TwoBoneIK3D.new()
	ik.name = "LegIK"
	add_child(ik)
	ik.set_setting_count(1)
	ik.set_root_bone_name(0, "LeftUpLeg")
	ik.set_middle_bone_name(0, "LeftLeg")
	ik.set_end_bone_name(0, "LeftFoot")
	ik.set_target_node(0, ik.get_path_to(left_foot_target))
	ik.set_pole_node(0, ik.get_path_to(left_knee_pole))
	ik.influence = 1.0
```

## Tween recipes (pop-in, shake, sequence with tween_await, looping hover)
```gdscript
extends Node2D

signal door_opened

var _tween: Tween


func pop_in(node: CanvasItem) -> void:
	node.scale = Vector2.ZERO
	var t := node.create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(node, "scale", Vector2.ONE, 0.35)


func shake(node: Node2D, strength := 8.0, steps := 6) -> void:
	if _tween:
		_tween.kill()
	var origin := node.position
	_tween = create_tween()
	for i in steps:
		var falloff := 1.0 - float(i) / steps
		_tween.tween_property(node, "position", origin + Vector2(randf_range(-1, 1), randf_range(-1, 1)) * strength * falloff, 0.04)
	_tween.tween_property(node, "position", origin, 0.04)


func cutscene(actor: Node2D, door_pos: Vector2) -> void:
	var t := create_tween()
	t.tween_property(actor, "position", door_pos, 1.2)
	t.tween_callback(func() -> void: door_opened.emit())
	t.tween_await(door_opened).set_timeout(3.0)  # 4.7: wait for a signal inside the sequence
	t.tween_property(actor, "modulate:a", 0.0, 0.4)


func hover_forever(node: Node2D) -> void:
	var t := node.create_tween().set_loops().set_trans(Tween.TRANS_SINE)
	t.tween_property(node, "position:y", -6.0, 0.8).as_relative()
	t.tween_property(node, "position:y", 6.0, 0.8).as_relative()
```

## Building an Animation in code (method + value tracks)
```gdscript
extends AnimationPlayer


func _ready() -> void:
	var anim := Animation.new()
	anim.length = 1.0
	anim.loop_mode = Animation.LOOP_LINEAR
	var t := anim.add_track(Animation.TYPE_VALUE)
	anim.track_set_path(t, ^"Sprite2D:modulate")
	anim.track_insert_key(t, 0.0, Color.WHITE)
	anim.track_insert_key(t, 0.5, Color(1, 0.4, 0.4))
	anim.track_insert_key(t, 1.0, Color.WHITE)
	var m := anim.add_track(Animation.TYPE_METHOD)
	anim.track_set_path(m, ^".")
	anim.track_insert_key(m, 0.5, {"method": &"_on_pulse", "args": []})
	var lib := AnimationLibrary.new()
	lib.add_animation(&"pulse", anim)
	add_animation_library(&"fx", lib)
	play(&"fx/pulse")


func _on_pulse() -> void:
	print("pulse")
```
