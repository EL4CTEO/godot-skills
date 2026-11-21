# Modding and DLC patterns (compiled by the tests)

## Mod loader autoload (first autoload: packs mount before anything loads)
```gdscript
extends Node

## Autoload "Mods", placed FIRST in the autoload list. Layout per mod:
##   <mods dir>/<id>.pck or <id>.zip  containing res://mods/<id>/mod.cfg and res://mods/<id>/main.gd
##   or a plain folder <mods dir>/<id>/ with mod.cfg + data files (data-only mod).

signal mods_loaded(loaded: PackedStringArray)

const GAME_VERSION := "1.2.0"
const ENABLED_CFG := "user://mods.cfg"

var manifests: Array[Dictionary] = []
var loaded: PackedStringArray = []
var problems: Dictionary[String, String] = {}  # id -> reason, shown in the mod menu


func _init() -> void:
	# _init runs before the main scene and before other autoloads' _ready: mount packs here.
	var enabled := _enabled_ids()
	for dir in _mod_dirs():
		_discover(dir, enabled)
	manifests.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.priority < b.priority)
	for m in manifests:
		_mount(m)


func _ready() -> void:
	for m in manifests:
		if m.id in loaded:
			_run_entry(m)
	mods_loaded.emit(loaded)


func _mod_dirs() -> PackedStringArray:
	var dirs := PackedStringArray(["user://mods"])
	if not OS.has_feature("editor"):
		dirs.append(OS.get_executable_path().get_base_dir().path_join("mods"))
	DirAccess.make_dir_recursive_absolute("user://mods")
	return dirs


func _enabled_ids() -> PackedStringArray:
	var cfg := ConfigFile.new()
	if cfg.load(ENABLED_CFG) != OK:
		return PackedStringArray()  # nothing enabled until the player opts in
	return cfg.get_value("mods", "enabled", PackedStringArray())


func _discover(dir: String, enabled: PackedStringArray) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for file_name in DirAccess.get_files_at(dir):
		if file_name.get_extension() in ["pck", "zip"]:
			_add(_read_manifest_from_pack(dir.path_join(file_name)), dir.path_join(file_name), enabled)
	for sub in DirAccess.get_directories_at(dir):
		var cfg := ConfigFile.new()
		if cfg.load(dir.path_join(sub).path_join("mod.cfg")) == OK:
			_add(_manifest_from_cfg(cfg), dir.path_join(sub), enabled)


func _read_manifest_from_pack(path: String) -> Dictionary:
	if path.get_extension() != "zip":
		# A .pck can't be read before mounting; use the file name as id and check after mounting.
		return {"id": path.get_file().get_basename(), "version": "?", "game_version": "", "priority": 0, "depends": PackedStringArray()}
	var zip := ZIPReader.new()
	if zip.open(path) != OK:
		return {}
	var cfg_path := ""
	for f in zip.get_files():
		if f.ends_with("mod.cfg"):
			cfg_path = f
	var cfg := ConfigFile.new()
	var ok := cfg_path != "" and cfg.parse(zip.read_file(cfg_path).get_string_from_utf8()) == OK
	zip.close()
	return _manifest_from_cfg(cfg) if ok else {}


func _manifest_from_cfg(cfg: ConfigFile) -> Dictionary:
	return {
		"id": str(cfg.get_value("mod", "id", "")),
		"name": str(cfg.get_value("mod", "name", "")),
		"version": str(cfg.get_value("mod", "version", "0")),
		"game_version": str(cfg.get_value("mod", "game_version", "")),
		"priority": int(cfg.get_value("mod", "priority", 0)),
		"depends": PackedStringArray(cfg.get_value("mod", "depends", PackedStringArray())),
	}


func _add(m: Dictionary, path: String, enabled: PackedStringArray) -> void:
	if m.is_empty() or str(m.id).is_empty():
		problems[path.get_file()] = "missing or invalid mod.cfg"
		return
	if not (m.id in enabled):
		return
	if m.game_version != "" and m.game_version.naturalnocasecmp_to(GAME_VERSION) > 0:
		problems[m.id] = "needs game %s or newer" % m.game_version
		return
	m["path"] = path
	manifests.append(m)


func _mount(m: Dictionary) -> void:
	for dep in m.depends:
		if not (dep in loaded):
			problems[m.id] = "missing dependency %s" % dep
			return
	var path: String = m.path
	if path.get_extension() in ["pck", "zip"]:
		if not ProjectSettings.load_resource_pack(path, true):
			problems[m.id] = "could not mount pack"
			return
	loaded.append(m.id)


func _run_entry(m: Dictionary) -> void:
	var entry := "res://mods/%s/main.gd" % m.id
	if not ResourceLoader.exists(entry):
		return  # data-only mod
	var script := load(entry) as GDScript
	if script == null:
		problems[m.id] = "main.gd failed to load"
		return
	var instance: Object = script.new()
	if instance.has_method(&"_mod_init"):
		instance.call(&"_mod_init", ModApi.new())
	if instance is Node:
		add_child(instance)


func set_enabled(ids: PackedStringArray) -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("mods", "enabled", ids)
	cfg.save(ENABLED_CFG)  # takes effect on next start: packs must mount before loading


class ModApi:
	## The only surface mods get. Keep it small and versioned.
	const API_VERSION := 1

	func register_item(id: StringName, item: Resource) -> void:
		ContentRegistry.register(&"items", id, item)

	func register_scene(kind: StringName, id: StringName, scene: PackedScene) -> void:
		ContentRegistry.register(kind, id, scene)
```

## Content registry (the game reads content only from here)
```gdscript
class_name ContentRegistry
extends RefCounted

static var _tables: Dictionary[StringName, Dictionary] = {}


static func register(kind: StringName, id: StringName, value: Variant) -> void:
	if not _tables.has(kind):
		_tables[kind] = {}
	if _tables[kind].has(id):
		push_warning("%s '%s' overridden by a mod" % [kind, id])
	_tables[kind][id] = value


static func get_entry(kind: StringName, id: StringName) -> Variant:
	return _tables.get(kind, {}).get(id)


static func ids(kind: StringName) -> Array:
	return _tables.get(kind, {}).keys()
```

## Runtime loading for data mods (images, audio, glTF, JSON)
```gdscript
extends RefCounted

const MAX_TEXTURE_SIZE := 2048


static func load_texture(path: String) -> Texture2D:
	var img := Image.load_from_file(path)
	if img == null or img.is_empty():
		return null
	if maxi(img.get_width(), img.get_height()) > MAX_TEXTURE_SIZE:
		var s := float(MAX_TEXTURE_SIZE) / maxi(img.get_width(), img.get_height())
		img.resize(int(img.get_width() * s), int(img.get_height() * s))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


static func load_audio(path: String) -> AudioStream:
	match path.get_extension().to_lower():
		"ogg":
			return AudioStreamOggVorbis.load_from_file(path)
		"wav":
			return AudioStreamWAV.load_from_file(path)
		"mp3":
			return AudioStreamMP3.load_from_file(path)
	return null


static func load_model(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(path, state) != OK:
		return null
	return doc.generate_scene(state) as Node3D


static func load_json_dict(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var data: Variant = JSON.parse_string(text)
	return data if data is Dictionary else {}
```

## Build a shareable PCK from inside the game (level editor export)
```gdscript
extends Node


## Packs a saved level scene and its thumbnail under res://mods/<id>/.
func export_level_pack(mod_id: String, level_tscn: String, thumbnail_png: String, out_path: String) -> Error:
	var packer := PCKPacker.new()
	var err := packer.pck_start(out_path)
	if err != OK:
		return err
	var base := "res://mods/%s/" % mod_id
	var cfg := ConfigFile.new()
	cfg.set_value("mod", "id", mod_id)
	cfg.set_value("mod", "version", "1")
	var cfg_tmp := "user://_tmp_mod.cfg"
	cfg.save(cfg_tmp)
	packer.add_file(base + "mod.cfg", cfg_tmp)
	packer.add_file(base + "level.tscn", level_tscn)
	packer.add_file(base + "thumb.png", thumbnail_png)
	err = packer.flush()
	DirAccess.remove_absolute(cfg_tmp)
	return err
```

## DLC gate (ownership check, then mount)
```csharp
using Godot;

public partial class DlcManager : Node
{
    [Signal] public delegate void DlcMountedEventHandler(string id);

    /// <summary>Platform ownership check. Wire it to GodotSteam (isDLCInstalled) or a store plugin.</summary>
    public System.Func<string, bool> OwnsDlc { get; set; } = _ => OS.IsDebugBuild();

    public bool TryMount(string id)
    {
        string path = OS.GetExecutablePath().GetBaseDir().PathJoin($"dlc/{id}.pck");
        if (!OwnsDlc(id) || !FileAccess.FileExists(path))
            return false;
        // replaceFiles: false -> DLC can add files but never overwrite base-game files.
        if (!ProjectSettings.LoadResourcePack(path, false))
        {
            GD.PushWarning($"DLC {id}: failed to mount {path}");
            return false;
        }
        EmitSignal(SignalName.DlcMounted, id);
        return true;
    }
}
```
