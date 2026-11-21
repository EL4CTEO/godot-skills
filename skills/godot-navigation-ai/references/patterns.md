# Navigation and AI patterns (compiled by the tests)

## 3D agent with avoidance (CharacterBody3D)
```gdscript
extends CharacterBody3D

@export var speed := 4.0
@export var turn_speed := 10.0

@onready var agent: NavigationAgent3D = $NavigationAgent3D


func _ready() -> void:
	agent.velocity_computed.connect(_on_velocity_computed)
	agent.link_reached.connect(_on_link_reached)
	# The navigation map syncs on the first physics frame; querying earlier returns an empty path.
	await get_tree().physics_frame


func go_to(target: Vector3) -> void:
	agent.target_position = target


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	if agent.is_navigation_finished():
		_apply_velocity(Vector3(0.0, velocity.y, 0.0))
		return
	var next := agent.get_next_path_position()
	var dir := global_position.direction_to(next)
	dir.y = 0.0
	var desired := dir.normalized() * speed
	if dir.length_squared() > 0.001:
		var look := Basis.looking_at(dir)
		basis = basis.slerp(look, clampf(turn_speed * delta, 0.0, 1.0)).orthonormalized()
	if agent.avoidance_enabled:
		agent.velocity = Vector3(desired.x, velocity.y, desired.z)  # result arrives in velocity_computed
	else:
		_apply_velocity(Vector3(desired.x, velocity.y, desired.z))


func _on_velocity_computed(safe_velocity: Vector3) -> void:
	_apply_velocity(safe_velocity)


func _apply_velocity(v: Vector3) -> void:
	velocity = v
	move_and_slide()


func _on_link_reached(details: Dictionary) -> void:
	# details has "owner" (the NavigationLink3D), "position", "link_entry_position", "link_exit_position".
	print("using link ", details.get("owner"))
```
```csharp
using Godot;

public partial class Chaser : CharacterBody3D
{
    [Export] public float Speed { get; set; } = 4f;

    private NavigationAgent3D _agent = null!;

    public override async void _Ready()
    {
        _agent = GetNode<NavigationAgent3D>("NavigationAgent3D");
        _agent.VelocityComputed += OnVelocityComputed;
        await ToSignal(GetTree(), SceneTree.SignalName.PhysicsFrame);
    }

    public void GoTo(Vector3 target) => _agent.TargetPosition = target;

    public override void _PhysicsProcess(double delta)
    {
        Vector3 v = Velocity;
        if (!IsOnFloor())
            v += GetGravity() * (float)delta;
        if (_agent.IsNavigationFinished())
        {
            Move(new Vector3(0, v.Y, 0));
            return;
        }
        Vector3 dir = GlobalPosition.DirectionTo(_agent.GetNextPathPosition()) with { Y = 0 };
        Vector3 desired = dir.Normalized() * Speed;
        desired.Y = v.Y;
        if (_agent.AvoidanceEnabled)
            _agent.Velocity = desired;
        else
            Move(desired);
    }

    private void OnVelocityComputed(Vector3 safeVelocity) => Move(safeVelocity);

    private void Move(Vector3 v)
    {
        Velocity = v;
        MoveAndSlide();
    }
}
```

## 2D agent (top-down)
```gdscript
extends CharacterBody2D

@export var speed := 160.0

@onready var agent: NavigationAgent2D = $NavigationAgent2D


func _ready() -> void:
	agent.velocity_computed.connect(func(v: Vector2) -> void:
		velocity = v
		move_and_slide())


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Snap the click to the navmesh so unreachable clicks still give a sensible goal.
		var map := get_world_2d().navigation_map
		agent.target_position = NavigationServer2D.map_get_closest_point(map, get_global_mouse_position())


func _physics_process(_delta: float) -> void:
	if agent.is_navigation_finished():
		return
	var desired := global_position.direction_to(agent.get_next_path_position()) * speed
	if agent.avoidance_enabled:
		agent.velocity = desired
	else:
		velocity = desired
		move_and_slide()
```

## Runtime navmesh rebake (procedural levels, opened doors)
```gdscript
extends NavigationRegion3D

## Rebakes after level geometry changes. Coalesces rapid requests into one bake.

var _pending := false


func _ready() -> void:
	bake_finished.connect(_on_bake_finished)


func request_rebake() -> void:
	if is_baking():
		_pending = true
		return
	bake_navigation_mesh(true)  # threaded: no frame hitch


func _on_bake_finished() -> void:
	if _pending:
		_pending = false
		bake_navigation_mesh(true)
```

## Bake chunks through the server (parse on main thread, bake async)
```gdscript
extends Node3D

@export var template: NavigationMesh

var _region_rid: RID


func _ready() -> void:
	_region_rid = NavigationServer3D.region_create()
	NavigationServer3D.region_set_map(_region_rid, get_world_3d().navigation_map)


func bake_chunk(chunk_root: Node3D) -> void:
	var nav_mesh: NavigationMesh = template.duplicate()
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(nav_mesh, source, chunk_root)
	NavigationServer3D.bake_from_source_geometry_data_async(nav_mesh, source,
			_on_baked.bind(nav_mesh))


func _on_baked(nav_mesh: NavigationMesh) -> void:
	NavigationServer3D.region_set_navigation_mesh(_region_rid, nav_mesh)


func _exit_tree() -> void:
	NavigationServer3D.free_rid(_region_rid)
```

## Path query with costs and filters (no agent)
```gdscript
extends Node3D


func find_path(from: Vector3, to: Vector3, layers := 1) -> PackedVector3Array:
	var params := NavigationPathQueryParameters3D.new()
	params.map = get_world_3d().navigation_map
	params.start_position = from
	params.target_position = to
	params.navigation_layers = layers
	params.simplify_path = true
	params.simplify_epsilon = 0.25
	var result := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(params, result)
	return result.path


func random_wander_point(layers := 1) -> Vector3:
	return NavigationServer3D.map_get_random_point(get_world_3d().navigation_map, layers, true)
```

## Grid pathfinding with AStarGrid2D (tactics, roguelike)
```gdscript
extends Node2D

@export var walls: TileMapLayer
@export var swamp_cost := 3.0

var grid := AStarGrid2D.new()


func _ready() -> void:
	grid.region = walls.get_used_rect()
	grid.cell_size = Vector2(walls.tile_set.tile_size)
	grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	grid.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	grid.update()  # required after region/cell_size changes, before any query
	for cell in walls.get_used_cells():
		var data := walls.get_cell_tile_data(cell)
		if data and data.get_custom_data("solid"):
			grid.set_point_solid(cell)
		elif data and data.get_custom_data("swamp"):
			grid.set_point_weight_scale(cell, swamp_cost)


func path_cells(from: Vector2i, to: Vector2i) -> Array[Vector2i]:
	if not grid.is_in_boundsv(from) or not grid.is_in_boundsv(to):
		return []
	return grid.get_id_path(from, to, true)  # partial path if the goal is blocked


func path_world(from_world: Vector2, to_world: Vector2) -> PackedVector2Array:
	var from := walls.local_to_map(walls.to_local(from_world))
	var to := walls.local_to_map(walls.to_local(to_world))
	var out := PackedVector2Array()
	for cell in path_cells(from, to):
		out.append(walls.to_global(walls.map_to_local(cell)))
	return out
```
```csharp
using Godot;
using Godot.Collections;

public partial class GridPathfinder : Node
{
    private readonly AStarGrid2D _grid = new();

    public void Build(Rect2I region, Vector2 cellSize, System.Collections.Generic.IEnumerable<Vector2I> solid)
    {
        _grid.Region = region;
        _grid.CellSize = cellSize;
        _grid.DiagonalMode = AStarGrid2D.DiagonalModeEnum.OnlyIfNoObstacles;
        _grid.Update();
        foreach (Vector2I cell in solid)
            _grid.SetPointSolid(cell);
    }

    public Array<Vector2I> FindPath(Vector2I from, Vector2I to) =>
        _grid.IsInBoundsv(from) && _grid.IsInBoundsv(to) ? _grid.GetIdPath(from, to, true) : new Array<Vector2I>();
}
```

## Enemy brain: enum states, timed decisions, perception
```gdscript
extends CharacterBody3D

enum State { PATROL, CHASE, SEARCH, ATTACK }

@export var patrol_points: Array[Marker3D] = []
@export var sight_range := 15.0
@export var fov_degrees := 110.0
@export var attack_range := 1.8
@export_flags_3d_physics var sight_mask := 1

var state := State.PATROL
var target: Node3D
var last_known_position := Vector3.ZERO
var _patrol_index := 0

@onready var agent: NavigationAgent3D = $NavigationAgent3D
@onready var think: Timer = $ThinkTimer


func _ready() -> void:
	think.wait_time = randf_range(0.15, 0.3)  # stagger AI updates across enemies
	think.timeout.connect(_think)
	think.start()


func _think() -> void:
	var player := get_tree().get_first_node_in_group(&"player") as Node3D
	var sees := player != null and can_see(player)
	if sees:
		target = player
		last_known_position = player.global_position
	match state:
		State.PATROL:
			if sees:
				_enter(State.CHASE)
			elif agent.is_navigation_finished() and not patrol_points.is_empty():
				_patrol_index = (_patrol_index + 1) % patrol_points.size()
				agent.target_position = patrol_points[_patrol_index].global_position
		State.CHASE:
			if not sees:
				_enter(State.SEARCH)
			elif global_position.distance_to(target.global_position) <= attack_range:
				_enter(State.ATTACK)
			else:
				agent.target_position = target.global_position
		State.SEARCH:
			if sees:
				_enter(State.CHASE)
			elif agent.is_navigation_finished():
				_enter(State.PATROL)
		State.ATTACK:
			if not sees or global_position.distance_to(target.global_position) > attack_range * 1.2:
				_enter(State.CHASE)


func _enter(next: State) -> void:
	state = next
	match next:
		State.SEARCH:
			agent.target_position = last_known_position
		State.ATTACK:
			agent.target_position = global_position


func can_see(other: Node3D) -> bool:
	var eye := global_position + Vector3.UP * 1.6
	var to_other := other.global_position + Vector3.UP - eye
	if to_other.length() > sight_range:
		return false  # cheapest check first
	var forward := -global_basis.z
	if forward.dot(to_other.normalized()) < cos(deg_to_rad(fov_degrees * 0.5)):
		return false
	var query := PhysicsRayQueryParameters3D.create(eye, eye + to_other, sight_mask, [get_rid()])
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	return hit.is_empty() or hit.collider == other


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	if agent.is_navigation_finished():
		velocity.x = 0.0
		velocity.z = 0.0
	else:
		var dir := global_position.direction_to(agent.get_next_path_position())
		var speed := 5.0 if state == State.CHASE else 2.5
		velocity.x = dir.x * speed
		velocity.z = dir.z * speed
	move_and_slide()
```

## Hearing: a global noise event
```gdscript
extends Node3D

## Listener component: put it on any AI. Emitters call NoiseListener3D.emit_noise(...).

signal heard(position: Vector3)

@export var hearing_multiplier := 1.0


func _ready() -> void:
	add_to_group(&"noise_listeners")


static func emit_noise(tree: SceneTree, origin: Vector3, radius: float) -> void:
	tree.call_group(&"noise_listeners", &"on_noise", origin, radius)


func on_noise(origin: Vector3, radius: float) -> void:
	if global_position.distance_to(origin) <= radius * hearing_multiplier:
		heard.emit(origin)
```

## Minimal behavior tree (no addon)
```gdscript
class_name BTNode
extends RefCounted

## Tiny behavior tree: composites and leaves return SUCCESS, FAILURE or RUNNING each tick.

enum Status { SUCCESS, FAILURE, RUNNING }


func tick(_actor: Node, _bb: Dictionary) -> Status:
	return Status.SUCCESS


class Sequence extends BTNode:
	var children: Array[BTNode]

	func _init(nodes: Array[BTNode]) -> void:
		children = nodes

	func tick(actor: Node, bb: Dictionary) -> Status:
		for child in children:
			var s := child.tick(actor, bb)
			if s != Status.SUCCESS:
				return s
		return Status.SUCCESS


class Selector extends BTNode:
	var children: Array[BTNode]

	func _init(nodes: Array[BTNode]) -> void:
		children = nodes

	func tick(actor: Node, bb: Dictionary) -> Status:
		for child in children:
			var s := child.tick(actor, bb)
			if s != Status.FAILURE:
				return s
		return Status.FAILURE


class Condition extends BTNode:
	var check: Callable

	func _init(predicate: Callable) -> void:
		check = predicate

	func tick(actor: Node, bb: Dictionary) -> Status:
		return Status.SUCCESS if check.call(actor, bb) else Status.FAILURE


class Action extends BTNode:
	var run: Callable

	func _init(callable: Callable) -> void:
		run = callable

	func tick(actor: Node, bb: Dictionary) -> Status:
		return run.call(actor, bb)
```
```gdscript
extends Node

## Builds a tree from BTNode and ticks it on a timer.

var root: BTNode
var blackboard := {}


func _ready() -> void:
	root = BTNode.Selector.new([
		BTNode.Sequence.new([
			BTNode.Condition.new(func(_a: Node, bb: Dictionary) -> bool: return bb.get("health", 100) < 25),
			BTNode.Action.new(_flee),
		]),
		BTNode.Sequence.new([
			BTNode.Condition.new(func(_a: Node, bb: Dictionary) -> bool: return bb.has("target")),
			BTNode.Action.new(_attack),
		]),
		BTNode.Action.new(_wander),
	])
	var t := Timer.new()
	t.wait_time = 0.2
	t.autostart = true
	t.timeout.connect(func() -> void: root.tick(get_parent(), blackboard))
	add_child(t)


func _flee(_actor: Node, _bb: Dictionary) -> BTNode.Status:
	return BTNode.Status.RUNNING


func _attack(_actor: Node, _bb: Dictionary) -> BTNode.Status:
	return BTNode.Status.SUCCESS


func _wander(_actor: Node, _bb: Dictionary) -> BTNode.Status:
	return BTNode.Status.RUNNING
```

## Utility AI: score actions, pick the best
```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using Godot;

public sealed record UtilityAction(string Name, Func<Node, float> Score, Action<Node> Execute);

public partial class UtilityBrain : Node
{
    [Export] public double ThinkInterval { get; set; } = 0.25;
    [Export] public float Inertia { get; set; } = 0.1f; // bonus that keeps the current action, prevents flip-flopping

    public List<UtilityAction> Actions { get; } = new();
    public UtilityAction? Current { get; private set; }

    private double _timer;

    public override void _Process(double delta)
    {
        _timer -= delta;
        if (_timer > 0 || Actions.Count == 0)
            return;
        _timer = ThinkInterval;
        Node actor = GetParent();
        UtilityAction best = Actions
            .OrderByDescending(a => a.Score(actor) + (a == Current ? Inertia : 0f))
            .First();
        if (best != Current)
        {
            Current = best;
            GD.Print($"{actor.Name} -> {best.Name}");
        }
        Current.Execute(actor);
    }
}
```
