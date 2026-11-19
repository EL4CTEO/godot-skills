# Editor tooling patterns (compiled by the test suite)

## Tool node: configuration warnings, dynamic properties, undoable generation
```gdscript
@tool
class_name Spawner3D
extends Node3D

enum Shape { CIRCLE, GRID }

@export var scene: PackedScene:
	set(value):
		scene = value
		update_configuration_warnings()
@export var shape := Shape.CIRCLE:
	set(value):
		shape = value
		notify_property_list_changed()  # re-run _validate_property
@export var radius := 5.0
@export var columns := 4
@export_tool_button("Generate", "Add") var generate_action := generate


func _get_configuration_warnings() -> PackedStringArray:
	return PackedStringArray() if scene else PackedStringArray(["Assign a scene to spawn."])


func _validate_property(property: Dictionary) -> void:
	if property.name == "radius" and shape != Shape.CIRCLE:
		property.usage = PROPERTY_USAGE_NO_EDITOR
	if property.name == "columns" and shape != Shape.GRID:
		property.usage = PROPERTY_USAGE_NO_EDITOR


func generate() -> void:
	if not Engine.is_editor_hint() or scene == null:
		return
	var ur := EditorInterface.get_editor_undo_redo()
	ur.create_action("Generate spawns")
	for i in 8:
		var inst := scene.instantiate() as Node3D
		inst.position = _point(i)
		ur.add_do_method(self, &"add_child", inst, true)
		ur.add_do_property(inst, &"owner", get_tree().edited_scene_root)
		ur.add_do_reference(inst)
		ur.add_undo_method(self, &"remove_child", inst)
	ur.commit_action()


func _point(i: int) -> Vector3:
	if shape == Shape.CIRCLE:
		var a := TAU * i / 8.0
		return Vector3(cos(a), 0, sin(a)) * radius
	return Vector3(i % columns, 0, i / columns) * 2.0
```

## EditorScript: batch-fix every scene in a folder
```gdscript
@tool
extends EditorScript

const ROOT := "res://levels"


func _run() -> void:
	var fixed := 0
	for file in DirAccess.get_files_at(ROOT):
		if not file.ends_with(".tscn"):
			continue
		var path := ROOT.path_join(file)
		var root := (load(path) as PackedScene).instantiate()
		for light in root.find_children("*", "OmniLight3D", true, false):
			(light as OmniLight3D).shadow_enabled = false
			fixed += 1
		var packed := PackedScene.new()
		packed.pack(root)
		ResourceSaver.save(packed, path)
		root.free()
	EditorInterface.get_resource_filesystem().scan()
	print("disabled shadows on %d lights" % fixed)
```

## EditorPlugin with an EditorDock (4.6+) and a tool menu entry
```gdscript
@tool
extends EditorPlugin

var _dock: EditorDock


func _enter_tree() -> void:
	_dock = EditorDock.new()
	_dock.title = "Level Stats"
	_dock.default_slot = EditorDock.DOCK_SLOT_RIGHT_UL
	var label := Label.new()
	label.name = "Stats"
	_dock.add_child(label)
	add_dock(_dock)
	add_tool_menu_item("Refresh Level Stats", _refresh)
	scene_changed.connect(func(_root: Node) -> void: _refresh())


func _exit_tree() -> void:
	remove_tool_menu_item("Refresh Level Stats")
	if _dock:
		remove_dock(_dock)
		_dock.queue_free()


func _refresh() -> void:
	var root := EditorInterface.get_edited_scene_root()
	var label := _dock.get_node("Stats") as Label
	label.text = "No scene" if root == null else "%d nodes" % root.find_children("*", "", true, false).size()
```

## Inspector plugin: a button above every Spawner3D
```gdscript
@tool
extends EditorInspectorPlugin


func _can_handle(object: Object) -> bool:
	return object is Spawner3D


func _parse_begin(object: Object) -> void:
	var b := Button.new()
	b.text = "Generate now"
	b.pressed.connect((object as Spawner3D).generate)
	add_custom_control(b)
```

## Post-import script: collisions + materials on every reimport
```gdscript
@tool
extends EditorScenePostImport

const WALL_MATERIAL := "res://materials/wall.tres"


func _post_import(scene: Node) -> Object:
	for mesh in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := mesh as MeshInstance3D
		if mi.name.begins_with("Wall"):
			mi.create_trimesh_collision()
			if ResourceLoader.exists(WALL_MATERIAL):
				mi.material_override = load(WALL_MATERIAL)
	return scene  # returning null aborts the import
```

## Export plugin: strip dev files and add a build stamp
```gdscript
@tool
extends EditorExportPlugin


func _get_name() -> String:
	return "BuildStamp"


func _export_begin(_features: PackedStringArray, is_debug: bool, _path: String, _flags: int) -> void:
	var stamp := "%s %s" % [Time.get_datetime_string_from_system(true), "debug" if is_debug else "release"]
	add_file("res://build_stamp.txt", stamp.to_utf8_buffer(), false)


func _export_file(path: String, _type: String, _features: PackedStringArray) -> void:
	if path.begins_with("res://dev/") or path.ends_with(".md"):
		skip()
```

## C#: [Tool] node with configuration warnings
```csharp
using Godot;

[Tool]
[GlobalClass]
public partial class PatrolPath : Path3D
{
    [Export] public float WaitSeconds { get; set; } = 1f;

    public override string[] _GetConfigurationWarnings() =>
        Curve is null || Curve.PointCount < 2 ? new[] { "Patrol needs at least 2 curve points." } : System.Array.Empty<string>();

    public override void _Ready()
    {
        if (Engine.IsEditorHint())
            CurveChanged += UpdateConfigurationWarnings;
    }
}
```
