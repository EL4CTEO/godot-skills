# Compile-checks GDScript files for gd_check.py. Extends SceneTree so autoload names resolve, but
# frees the autoload nodes before they enter the tree (their _ready() never runs).
extends SceneTree


func _initialize() -> void:
	for autoload in root.get_children():
		root.remove_child(autoload)
		autoload.free()
	var list := OS.get_cmdline_user_args()
	var paths := FileAccess.get_file_as_string(list[0]).split("\n", false) if list.size() > 0 else PackedStringArray()
	for raw_path in paths:
		var path := raw_path.strip_edges()
		print("@@FILE ", path)
		var s := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
		print("@@DONE ", path, " ", s != null)
	quit(0)
