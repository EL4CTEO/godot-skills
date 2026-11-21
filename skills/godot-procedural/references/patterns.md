# Procedural generation patterns (compiled by the tests)

## Seeded noise world on a TileMapLayer (height + moisture biomes)
```gdscript
extends TileMapLayer

@export var world_seed := 12345
@export var size := Vector2i(128, 96)
@export var source_id := 0

const WATER := Vector2i(0, 0)
const SAND := Vector2i(1, 0)
const GRASS := Vector2i(2, 0)
const FOREST := Vector2i(3, 0)
const ROCK := Vector2i(4, 0)

var height := FastNoiseLite.new()
var moisture := FastNoiseLite.new()


func _ready() -> void:
	generate(world_seed)


func generate(seed_value: int) -> void:
	height.seed = seed_value
	height.frequency = 0.02
	height.fractal_octaves = 5
	moisture.seed = seed_value + 1  # independent noise per channel
	moisture.frequency = 0.03
	clear()
	for x in size.x:
		for y in size.y:
			set_cell(Vector2i(x, y), source_id, _biome(x, y))


func _biome(x: int, y: int) -> Vector2i:
	var h := (height.get_noise_2d(x, y) + 1.0) * 0.5
	# fall off toward the edges to make an island
	var edge := Vector2(x, y) / Vector2(size) * 2.0 - Vector2.ONE
	h -= edge.length_squared() * 0.35
	var m := (moisture.get_noise_2d(x, y) + 1.0) * 0.5
	if h < 0.3:
		return WATER
	if h < 0.35:
		return SAND
	if h > 0.75:
		return ROCK
	return FOREST if m > 0.55 else GRASS
```

## Cellular-automata caves (data first, then terrain autotile)
```gdscript
extends RefCounted

## Returns a Dictionary[Vector2i, bool] (true = wall). Deterministic for a given rng seed.


static func generate(rng: RandomNumberGenerator, size: Vector2i, fill := 0.47, passes := 5) -> Dictionary[Vector2i, bool]:
	var walls: Dictionary[Vector2i, bool] = {}
	for x in size.x:
		for y in size.y:
			var border := x == 0 or y == 0 or x == size.x - 1 or y == size.y - 1
			walls[Vector2i(x, y)] = border or rng.randf() < fill
	for i in passes:
		var next: Dictionary[Vector2i, bool] = {}
		for cell: Vector2i in walls:
			var n := 0
			for dx in range(-1, 2):
				for dy in range(-1, 2):
					if (dx != 0 or dy != 0) and walls.get(cell + Vector2i(dx, dy), true):
						n += 1
			next[cell] = n >= 5 or (walls[cell] and n >= 4)
		walls = next
	return walls


static func apply(layer: TileMapLayer, walls: Dictionary[Vector2i, bool], terrain_set := 0, terrain := 0) -> void:
	var wall_cells: Array[Vector2i] = []
	for cell: Vector2i in walls:
		if walls[cell]:
			wall_cells.append(cell)
	layer.clear()
	layer.set_cells_terrain_connect(wall_cells, terrain_set, terrain)  # one call per terrain
```

## BSP dungeon: rooms + corridors, with a connectivity guarantee
```gdscript
extends RefCounted

## Splits a rect recursively, puts a room in each leaf, joins siblings with L-shaped corridors.

var rng := RandomNumberGenerator.new()
var rooms: Array[Rect2i] = []
var floor_cells: Dictionary[Vector2i, bool] = {}
var min_leaf := 10


func build(seed_value: int, area: Rect2i) -> void:
	rng.seed = seed_value
	rooms.clear()
	floor_cells.clear()
	_split(area, 0)


func _split(rect: Rect2i, depth: int) -> Vector2i:
	var can_h := rect.size.y >= min_leaf * 2
	var can_v := rect.size.x >= min_leaf * 2
	if depth > 6 or not (can_h or can_v):
		return _make_room(rect)
	var horizontal := can_h and (not can_v or rng.randf() < 0.5)
	var a: Rect2i
	var b: Rect2i
	if horizontal:
		var cut := rng.randi_range(min_leaf, rect.size.y - min_leaf)
		a = Rect2i(rect.position, Vector2i(rect.size.x, cut))
		b = Rect2i(rect.position + Vector2i(0, cut), Vector2i(rect.size.x, rect.size.y - cut))
	else:
		var cut := rng.randi_range(min_leaf, rect.size.x - min_leaf)
		a = Rect2i(rect.position, Vector2i(cut, rect.size.y))
		b = Rect2i(rect.position + Vector2i(cut, 0), Vector2i(rect.size.x - cut, rect.size.y))
	var ca := _split(a, depth + 1)
	var cb := _split(b, depth + 1)
	_corridor(ca, cb)
	return ca if rng.randf() < 0.5 else cb


func _make_room(leaf: Rect2i) -> Vector2i:
	var w := rng.randi_range(4, leaf.size.x - 2)
	var h := rng.randi_range(4, leaf.size.y - 2)
	var pos := leaf.position + Vector2i(rng.randi_range(1, leaf.size.x - w - 1), rng.randi_range(1, leaf.size.y - h - 1))
	var room := Rect2i(pos, Vector2i(w, h))
	rooms.append(room)
	for x in range(room.position.x, room.end.x):
		for y in range(room.position.y, room.end.y):
			floor_cells[Vector2i(x, y)] = true
	return room.get_center()


func _corridor(from: Vector2i, to: Vector2i) -> void:
	var corner := Vector2i(to.x, from.y) if rng.randf() < 0.5 else Vector2i(from.x, to.y)
	for seg: Array in [[from, corner], [corner, to]]:
		var p: Vector2i = seg[0]
		var end: Vector2i = seg[1]
		var step := (end - p).sign()
		while p != end:
			floor_cells[p] = true
			p += step
		floor_cells[p] = true


func is_connected_level() -> bool:
	if rooms.is_empty():
		return false
	var start := rooms[0].get_center()
	var seen: Dictionary[Vector2i, bool] = {start: true}
	var stack: Array[Vector2i] = [start]
	while not stack.is_empty():
		var c: Vector2i = stack.pop_back()
		for d: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var n := c + d
			if floor_cells.has(n) and not seen.has(n):
				seen[n] = true
				stack.append(n)
	return seen.size() == floor_cells.size()
```

## Poisson-disc scatter (even spacing for trees, rocks, spawn points)
```gdscript
extends RefCounted


static func poisson_disc(rng: RandomNumberGenerator, area: Vector2, radius: float, tries := 30) -> PackedVector2Array:
	var cell := radius / sqrt(2.0)
	var grid_size := Vector2i(ceili(area.x / cell), ceili(area.y / cell))
	var grid := PackedInt32Array()
	grid.resize(grid_size.x * grid_size.y)
	grid.fill(-1)
	var points := PackedVector2Array()
	var active: Array[int] = []
	var first := Vector2(rng.randf() * area.x, rng.randf() * area.y)
	points.append(first)
	active.append(0)
	grid[int(first.y / cell) * grid_size.x + int(first.x / cell)] = 0
	while not active.is_empty():
		var idx := rng.randi_range(0, active.size() - 1)
		var origin := points[active[idx]]
		var placed := false
		for t in tries:
			var p := origin + Vector2.from_angle(rng.randf() * TAU) * rng.randf_range(radius, radius * 2.0)
			if p.x < 0 or p.y < 0 or p.x >= area.x or p.y >= area.y:
				continue
			var gp := Vector2i(int(p.x / cell), int(p.y / cell))
			var ok := true
			for x in range(maxi(gp.x - 2, 0), mini(gp.x + 3, grid_size.x)):
				for y in range(maxi(gp.y - 2, 0), mini(gp.y + 3, grid_size.y)):
					var other := grid[y * grid_size.x + x]
					if other != -1 and points[other].distance_squared_to(p) < radius * radius:
						ok = false
			if ok:
				grid[gp.y * grid_size.x + gp.x] = points.size()
				active.append(points.size())
				points.append(p)
				placed = true
				break
		if not placed:
			active.remove_at(idx)
	return points
```

## Weighted loot table as a Resource
```gdscript
class_name LootTable
extends Resource

@export var items: Array[StringName] = []
@export var weights: PackedFloat32Array = []
@export var nothing_weight := 0.0


func roll(rng: RandomNumberGenerator) -> StringName:
	var all := weights.duplicate()
	all.append(nothing_weight)
	var i := rng.rand_weighted(all)
	return &"" if i < 0 or i >= items.size() else items[i]
```

## Heightmap terrain chunk: mesh + HeightMapShape3D collision
```gdscript
extends StaticBody3D

@export var noise: FastNoiseLite
@export var resolution := 64  # quads per side
@export var spacing := 1.0
@export var amplitude := 12.0
@export var material: Material


func _ready() -> void:
	if noise == null:
		noise = FastNoiseLite.new()
	build(Vector2i.ZERO)


func build(chunk: Vector2i) -> void:
	var verts := resolution + 1
	var heights := PackedFloat32Array()
	heights.resize(verts * verts)
	var origin := Vector2(chunk) * resolution
	for z in verts:
		for x in verts:
			heights[z * verts + x] = noise.get_noise_2d(origin.x + x, origin.y + z) * amplitude

	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var half := resolution * spacing * 0.5
	for z in verts:
		for x in verts:
			st.set_uv(Vector2(x, z) / resolution)
			st.add_vertex(Vector3(x * spacing - half, heights[z * verts + x], z * spacing - half))
	for z in resolution:
		for x in resolution:
			var i := z * verts + x
			st.add_index(i)
			st.add_index(i + 1)
			st.add_index(i + verts)
			st.add_index(i + 1)
			st.add_index(i + verts + 1)
			st.add_index(i + verts)
	st.generate_normals()
	if material:
		st.set_material(material)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	add_child(mi)

	var shape := HeightMapShape3D.new()
	shape.map_width = verts
	shape.map_depth = verts
	shape.map_data = heights
	var col := CollisionShape3D.new()
	col.shape = shape
	col.scale = Vector3(spacing, 1.0, spacing)  # heightmap cells are 1 unit apart
	add_child(col)
```

## Threaded chunk streaming (worker builds arrays, main thread adds nodes)
```gdscript
extends Node3D

@export var chunk_size := 32.0
@export var view_chunks := 3
@export var player: Node3D

var noise := FastNoiseLite.new()
var _loaded: Dictionary[Vector2i, Node3D] = {}
var _pending: Dictionary[Vector2i, int] = {}


func _process(_delta: float) -> void:
	if player == null:
		return
	var center := Vector2i(floori(player.global_position.x / chunk_size), floori(player.global_position.z / chunk_size))
	for x in range(center.x - view_chunks, center.x + view_chunks + 1):
		for z in range(center.y - view_chunks, center.y + view_chunks + 1):
			var c := Vector2i(x, z)
			if not _loaded.has(c) and not _pending.has(c):
				_pending[c] = WorkerThreadPool.add_task(_build_arrays.bind(c), false, "chunk %s" % c)
	for c: Vector2i in _loaded.keys():
		if absi(c.x - center.x) > view_chunks + 1 or absi(c.y - center.y) > view_chunks + 1:
			_loaded[c].queue_free()
			_loaded.erase(c)


func _build_arrays(c: Vector2i) -> void:
	# Worker thread: pure data only. No add_child, no node access.
	var verts := PackedVector3Array()
	var n := 16
	var step := chunk_size / n
	for z in n + 1:
		for x in n + 1:
			var wx := c.x * chunk_size + x * step
			var wz := c.y * chunk_size + z * step
			verts.append(Vector3(x * step, noise.get_noise_2d(wx, wz) * 8.0, z * step))
	var idx := PackedInt32Array()
	for z in n:
		for x in n:
			var i := z * (n + 1) + x
			idx.append_array([i, i + 1, i + n + 1, i + 1, i + n + 2, i + n + 1])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_INDEX] = idx
	_finish.call_deferred(c, arrays)


func _finish(c: Vector2i, arrays: Array) -> void:
	WorkerThreadPool.wait_for_task_completion(_pending[c])
	_pending.erase(c)
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = Vector3(c.x * chunk_size, 0.0, c.y * chunk_size)
	add_child(mi)
	_loaded[c] = mi
```

## Seeded generator in C# (fill an Image from noise)
```csharp
using Godot;

public partial class NoiseMapBaker : Node
{
    [Export] public int Seed { get; set; } = 1337;
    [Export] public Vector2I Size { get; set; } = new(256, 256);

    public ImageTexture Bake()
    {
        var noise = new FastNoiseLite
        {
            Seed = Seed,
            NoiseType = FastNoiseLite.NoiseTypeEnum.SimplexSmooth,
            Frequency = 0.01f,
            FractalOctaves = 5,
        };
        var rng = new RandomNumberGenerator { Seed = (ulong)Seed };
        Image img = Image.CreateEmpty(Size.X, Size.Y, false, Image.Format.Rgb8);
        for (int y = 0; y < Size.Y; y++)
        {
            for (int x = 0; x < Size.X; x++)
            {
                float h = (noise.GetNoise2D(x, y) + 1f) * 0.5f;
                float jitter = rng.RandfRange(-0.02f, 0.02f);
                img.SetPixel(x, y, new Color(h + jitter, h, h));
            }
        }
        return ImageTexture.CreateFromImage(img);
    }
}
```
