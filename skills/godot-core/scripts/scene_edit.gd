# Headless scene builder/editor used by scene_edit.py.
# Reads a JSON spec path from the user args, applies ops, saves the .tscn, prints RESULT_JSON.
# Extends SceneTree so autoload names are registered (scripts using them compile), but frees the
# autoload nodes before they enter the tree: their _ready() never runs (only _init()).
extends SceneTree

var errors: Array[String] = []
var scene_root: Node


func _initialize() -> void:
	for autoload in root.get_children():
		root.remove_child(autoload)
		autoload.free()
	var args := OS.get_cmdline_user_args()
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0])) if args.size() > 0 else {}
	var out := {}
	if spec.is_empty():
		errors.append("empty or invalid spec")
	else:
		out = _apply(spec)
	out["ok"] = errors.is_empty()
	out["errors"] = errors
	print("RESULT_JSON ", JSON.stringify(out))
	if scene_root:
		scene_root.free()
	quit(0)


func _apply(spec: Dictionary) -> Dictionary:
	var path: String = spec.get("scene", "")
	var created := false
	if spec.has("root") or spec.has("inherits") or not ResourceLoader.exists(path):
		created = true
		if spec.has("inherits"):
			var base: PackedScene = load(spec["inherits"])
			scene_root = base.instantiate(PackedScene.GEN_EDIT_STATE_MAIN_INHERITED)
		else:
			var r: Dictionary = spec.get("root", {"type": "Node"})
			scene_root = _make(r.get("type", "Node"), r.get("script", ""))
		if scene_root == null:
			errors.append("cannot create root")
			return {}
		var rd: Dictionary = spec.get("root", {})
		scene_root.name = rd.get("name", path.get_file().get_basename().to_pascal_case())
		_set_props(scene_root, rd.get("props", {}))
	else:
		var ps: PackedScene = load(path)
		scene_root = ps.instantiate(PackedScene.GEN_EDIT_STATE_MAIN)
	for op in spec.get("ops", []):
		_op(op)
	if spec.get("dry_run", false) or not errors.is_empty():
		return {"scene": path, "saved": false, "tree": _tree(scene_root, 0)}
	var packed := PackedScene.new()
	var err := packed.pack(scene_root)
	if err != OK:
		errors.append("pack failed: %s" % error_string(err))
		return {}
	var had_uid := ResourceLoader.get_resource_uid(path) != ResourceUID.INVALID_ID
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	err = ResourceSaver.save(packed, path)
	if err != OK:
		errors.append("save failed: %s" % error_string(err))
	elif created and not had_uid:
		ResourceSaver.set_uid(path, ResourceUID.create_id())
	return {"scene": path, "created": created, "saved": err == OK, "tree": _tree(scene_root, 0)}


func _make(type: String, script_path: String) -> Node:
	var n: Node
	if type.begins_with("res://") or type.begins_with("uid://"):
		n = (load(type) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	elif ClassDB.class_exists(type) and ClassDB.can_instantiate(type) and ClassDB.is_parent_class(type, "Node"):
		n = ClassDB.instantiate(type)
	else:
		errors.append("not an instantiable Node class: %s" % type)
		return null
	if script_path != "":
		_attach(n, script_path)
	return n


func _attach(n: Node, script_path: String) -> void:
	var s: Script = load(script_path) if ResourceLoader.exists(script_path) else null
	if s == null:
		errors.append("cannot load script %s (missing, or compile errors: run gd_check/cs_build)" % script_path)
		return
	n.set_script(s)
	if n.get_script() != s:
		errors.append("script %s cannot attach to %s (base class mismatch, or C# not built)" % [script_path, n.get_class()])


func _node(path: String) -> Node:
	if path in ["", "."]:
		return scene_root
	var n := scene_root.get_node_or_null(NodePath(path))
	if n == null:
		errors.append("node not found: %s" % path)
	return n


func _own(n: Node) -> void:
	# Owner = scene_root for the node; nodes inside an instanced scene keep their own owner.
	n.owner = scene_root
	if n.scene_file_path != "":
		return
	for c in n.get_children():
		_own(c)


func _op(op: Dictionary) -> void:
	match op.get("op", ""):
		"add", "instance":
			var parent := _node(op.get("parent", "."))
			var t: String = op.get("scene", op.get("type", "Node"))
			var n := _make(t, op.get("script", ""))
			if parent == null or n == null:
				return
			if op.has("name"):
				n.name = op["name"]
			parent.add_child(n, true)
			_own(n)
			_set_props(n, op.get("props", {}))
			if op.get("unique", false):
				n.unique_name_in_owner = true
		"set":
			var n := _node(op.get("node", "."))
			if n:
				_set_props(n, op.get("props", {}))
		"script":
			var n := _node(op.get("node", "."))
			if n:
				if op.get("path", "") != "":
					_attach(n, op["path"])
				else:
					n.set_script(null)
		"remove":
			var n := _node(op.get("node", ""))
			if n and n != scene_root:
				n.get_parent().remove_child(n)
				n.free()
		"rename":
			var n := _node(op.get("node", ""))
			if n:
				n.name = op["name"]
		"move":
			var n := _node(op.get("node", ""))
			var p := _node(op.get("parent", "."))
			if n and p and n != scene_root:
				n.reparent(p, op.get("keep_global", true))
				_own(n)
				if op.has("index"):
					p.move_child(n, int(op["index"]))
		"connect":
			var a := _node(op.get("from", "."))
			var b := _node(op.get("to", "."))
			if a and b:
				var err := a.connect(op["signal"], Callable(b, op["method"]), Object.CONNECT_PERSIST)
				if err != OK:
					errors.append("connect %s failed: %s" % [op["signal"], error_string(err)])
		"disconnect":
			var a := _node(op.get("from", "."))
			var b := _node(op.get("to", "."))
			if a and b and a.is_connected(op["signal"], Callable(b, op["method"])):
				a.disconnect(op["signal"], Callable(b, op["method"]))
		"group":
			var n := _node(op.get("node", "."))
			if n:
				if op.get("remove", false):
					n.remove_from_group(op["group"])
				else:
					n.add_to_group(op["group"], true)
		_:
			errors.append("unknown op: %s" % op.get("op", ""))


func _set_props(obj: Object, props: Dictionary) -> void:
	for key: String in props:
		var hint := _prop_info(obj, key)
		if hint.is_empty() and not key.contains(":"):
			errors.append("%s has no property '%s'" % [obj.get_class(), key])
			continue
		var want := int(hint.get("type", TYPE_NIL))
		var v: Variant = _convert(props[key], want)
		if want not in [TYPE_NIL, typeof(v)] and not (want == TYPE_FLOAT and v is int) 				and not (want == TYPE_OBJECT and v == null):
			errors.append("%s.%s expects %s, got %s (%s)" % [obj.get_class(), key, type_string(want), type_string(typeof(v)), str(props[key])])
			continue
		if key.contains(":"):
			obj.set_indexed(NodePath(key), v)
		else:
			obj.set(key, v)


func _prop_info(obj: Object, key: String) -> Dictionary:
	for p in obj.get_property_list():
		if p["name"] == key:
			return p
	return {}


func _convert(v: Variant, type: int) -> Variant:
	if v is Dictionary and (v.has("new") or v.has("load")):
		if v.has("load"):
			return load(v["load"])
		var res: Object = ClassDB.instantiate(v["new"])
		var rest: Dictionary = v.duplicate()
		rest.erase("new")
		_set_props(res, rest)
		return res
	if v is String:
		if type in [TYPE_STRING, TYPE_STRING_NAME]:
			return v
		if type == TYPE_NODE_PATH:
			return NodePath(v)
		if type == TYPE_OBJECT and (v.begins_with("res://") or v.begins_with("uid://")):
			return load(v)
		if v.is_valid_identifier():
			return v  # plain word: let the type check report it
		return _eval(v)
	if v is Array and type in [TYPE_VECTOR2, TYPE_VECTOR2I, TYPE_VECTOR3, TYPE_VECTOR3I, TYPE_VECTOR4, TYPE_COLOR]:
		return type_convert(_vec(v, type), type)
	if v is float and type == TYPE_INT:
		return int(v)
	return v


func _eval(code: String) -> Variant:
	# Any GDScript expression: Vector3(1, 2, 3), Color.RED, Vector3.UP * 2, deg_to_rad(90)
	var s := GDScript.new()
	s.source_code = "static func v() -> Variant:
	return %s
" % code
	if s.reload() != OK:
		errors.append("cannot parse value: %s" % code)
		return code
	return s.call("v")


func _vec(a: Array, type: int) -> Variant:
	match type:
		TYPE_VECTOR2, TYPE_VECTOR2I:
			return Vector2(a[0], a[1])
		TYPE_VECTOR3, TYPE_VECTOR3I:
			return Vector3(a[0], a[1], a[2])
		TYPE_COLOR:
			return Color(a[0], a[1], a[2], a[3] if a.size() > 3 else 1.0)
	return Vector4(a[0], a[1], a[2], a[3])


func _tree(n: Node, depth: int) -> Array:
	var line := "  ".repeat(depth) + "%s (%s)" % [n.name, n.get_class()]
	if n.scene_file_path != "" and n != scene_root:
		line += " [inst %s]" % n.scene_file_path
	var s: Script = n.get_script()
	if s:
		line += " script=%s" % s.resource_path
	var out := [line]
	if n.scene_file_path != "" and n != scene_root:
		return out
	for c in n.get_children():
		out.append_array(_tree(c, depth + 1))
	return out
