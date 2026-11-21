# Addon patterns (compiled by the tests)

## Optional dependency: use an addon only when it's present
```gdscript
extends Node

## Autoload "Platform". Game code calls these; missing plugins degrade gracefully.

var steam: Object


func _ready() -> void:
	if Engine.has_singleton("Steam"):
		steam = Engine.get_singleton("Steam")


func has_steam() -> bool:
	return steam != null


func unlock_achievement(id: String) -> void:
	if steam == null:
		print_verbose("achievement (no Steam): ", id)
		return
	steam.call("setAchievement", id)
	steam.call("storeStats")


## GDExtension classes exist only when the extension loaded on this platform.
func make_optional_node(gdextension_class: StringName, fallback: GDScript) -> Node:
	if ClassDB.class_exists(gdextension_class) and ClassDB.can_instantiate(gdextension_class):
		return ClassDB.instantiate(gdextension_class) as Node
	return fallback.new() as Node
```
```csharp
using Godot;

public partial class Platform : Node
{
    private GodotObject? _steam;

    public bool HasSteam => _steam is not null;

    public override void _Ready()
    {
        if (Engine.HasSingleton("Steam"))
            _steam = Engine.GetSingleton("Steam");
    }

    public void UnlockAchievement(string id)
    {
        if (_steam is null)
        {
            GD.Print($"achievement (no Steam): {id}");
            return;
        }
        _steam.Call("setAchievement", id);
        _steam.Call("storeStats");
    }

    public static Node? TryCreate(StringName gdextensionClass) =>
        ClassDB.ClassExists(gdextensionClass) && ClassDB.CanInstantiate(gdextensionClass)
            ? ClassDB.Instantiate(gdextensionClass).As<Node>()
            : null;
}
```

## Editor-only check: warn when a required plugin is disabled
```gdscript
@tool
extends Node

## Drop into a main scene during development. Warns in the editor if required plugins are off.

const REQUIRED: PackedStringArray = ["gdUnit4"]


func _ready() -> void:
	if not Engine.is_editor_hint():
		return
	var enabled: PackedStringArray = ProjectSettings.get_setting("editor_plugins/enabled", PackedStringArray())
	for plugin_name in REQUIRED:
		var path := "res://addons/%s/plugin.cfg" % plugin_name
		if FileAccess.file_exists(path) and not (path in enabled):
			push_warning("Plugin '%s' is installed but disabled (Project Settings > Plugins)" % plugin_name)
```
