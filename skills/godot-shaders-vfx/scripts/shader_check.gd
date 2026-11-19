# Validates .gdshader files for shader_check.py. The shader compiler front end (parser and
# semantic checks) runs even with the headless dummy renderer. Markers go to stderr so they
# interleave correctly with the engine's SHADER ERROR lines.
extends SceneTree


func _initialize() -> void:
	for autoload in root.get_children():
		root.remove_child(autoload)
		autoload.free()
	var list := OS.get_cmdline_user_args()
	var paths := FileAccess.get_file_as_string(list[0]).split("\n", false) if list.size() > 0 else PackedStringArray()
	for raw_path in paths:
		var path := raw_path.strip_edges()
		printerr("@@SHADER ", path)
		var sh := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as Shader
		if sh:
			sh.get_rid()  # forces preprocessing (#include) + compilation
			printerr("@@MODE ", path, " ", sh.get_mode())
	printerr("@@END")
	quit(0)
