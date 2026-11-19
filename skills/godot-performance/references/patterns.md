# Performance patterns (compiled by the test suite)

## In-game perf HUD + custom monitor (shows in the editor's Monitors tab too)
```gdscript
extends Label

var enemy_count := 0


func _ready() -> void:
	Performance.add_custom_monitor(&"game/enemies", func() -> int: return enemy_count)


func _exit_tree() -> void:
	if Performance.has_custom_monitor(&"game/enemies"):
		Performance.remove_custom_monitor(&"game/enemies")


func _process(_delta: float) -> void:
	text = "FPS %d | proc %.2f ms | phys %.2f ms | draws %d | nodes %d | orphans %d" % [
		Engine.get_frames_per_second(),
		Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT),
	]
```

## MultiMesh crowd: 10k instances, one draw call, bulk buffer upload
```gdscript
extends MultiMeshInstance3D

@export var count := 10000
@export var area := 200.0

var _positions := PackedVector3Array()
var _velocities := PackedVector3Array()
var _buffer := PackedFloat32Array()


func _ready() -> void:
	multimesh = MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = BoxMesh.new()
	multimesh.instance_count = count
	_positions.resize(count)
	_velocities.resize(count)
	_buffer.resize(count * 12)  # 3x4 transform per instance
	for i in count:
		_positions[i] = Vector3(randf_range(-area, area), 0.0, randf_range(-area, area))
		_velocities[i] = Vector3(randf_range(-1, 1), 0.0, randf_range(-1, 1)).normalized() * 3.0


func _process(delta: float) -> void:
	for i in count:
		var p := _positions[i] + _velocities[i] * delta
		if absf(p.x) > area or absf(p.z) > area:
			_velocities[i] = -_velocities[i]
		_positions[i] = p
		var o := i * 12  # row-major basis (identity) + origin
		_buffer[o] = 1.0; _buffer[o + 1] = 0.0; _buffer[o + 2] = 0.0; _buffer[o + 3] = p.x
		_buffer[o + 4] = 0.0; _buffer[o + 5] = 1.0; _buffer[o + 6] = 0.0; _buffer[o + 7] = p.y
		_buffer[o + 8] = 0.0; _buffer[o + 9] = 0.0; _buffer[o + 10] = 1.0; _buffer[o + 11] = p.z
	multimesh.buffer = _buffer
```

## Parallel work with WorkerThreadPool (results applied on the main thread)
```gdscript
extends Node

var _heights := PackedFloat32Array()
var _noise := FastNoiseLite.new()
const SIZE := 512


func generate() -> void:
	_heights.resize(SIZE * SIZE)
	var task := WorkerThreadPool.add_group_task(_row, SIZE, -1, false, "terrain rows")
	WorkerThreadPool.wait_for_group_task_completion(task)  # or poll is_group_task_completed() per frame
	_apply.call_deferred()


func _row(y: int) -> void:  # runs on worker threads: no scene tree access here
	for x in SIZE:
		_heights[y * SIZE + x] = _noise.get_noise_2d(x, y)


func _apply() -> void:
	assert(Thread.is_main_thread())
	print("terrain ready: ", _heights.size())
```

## Bullets without nodes (PhysicsServer2D query + RenderingServer canvas items)
```gdscript
extends Node2D

const SPEED := 900.0

@export var bullet_texture: Texture2D

var _bullets: Array[Dictionary] = []


func fire(from: Vector2, dir: Vector2) -> void:
	var ci := RenderingServer.canvas_item_create()
	RenderingServer.canvas_item_set_parent(ci, get_canvas_item())
	RenderingServer.canvas_item_add_texture_rect(ci, Rect2(-4, -4, 8, 8), bullet_texture.get_rid())
	_bullets.append({"pos": from, "vel": dir.normalized() * SPEED, "ci": ci, "life": 2.0})


func _physics_process(delta: float) -> void:
	var space := get_world_2d().direct_space_state
	for i in range(_bullets.size() - 1, -1, -1):
		var b := _bullets[i]
		var next: Vector2 = b.pos + b.vel * delta
		var hit := space.intersect_ray(PhysicsRayQueryParameters2D.create(b.pos, next))
		b.life -= delta
		if hit or b.life <= 0.0:
			RenderingServer.free_rid(b.ci)
			_bullets.remove_at(i)
			continue
		b.pos = next
		RenderingServer.canvas_item_set_transform(b.ci, Transform2D(0.0, next))


func _exit_tree() -> void:
	for b in _bullets:
		RenderingServer.free_rid(b.ci)
```

## C#: allocation-free hot loop
```csharp
using Godot;

public partial class Swarm : Node3D
{
    private static readonly StringName EnemiesGroup = "enemies";
    private Node3D[] _cache = System.Array.Empty<Node3D>();
    private float _refresh;

    public override void _PhysicsProcess(double delta)
    {
        _refresh -= (float)delta;
        if (_refresh <= 0f)
        {
            var nodes = GetTree().GetNodesInGroup(EnemiesGroup);   // allocates: do it rarely
            _cache = new Node3D[nodes.Count];
            for (int i = 0; i < nodes.Count; i++)
                _cache[i] = (Node3D)nodes[i];
            _refresh = 0.5f;
        }
        Vector3 target = GlobalPosition;
        foreach (Node3D enemy in _cache)                          // no LINQ, no closures
        {
            if (!IsInstanceValid(enemy))
                continue;
            enemy.GlobalPosition = enemy.GlobalPosition.MoveToward(target, 2f * (float)delta);
        }
    }
}
```
