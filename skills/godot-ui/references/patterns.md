# UI patterns (compiled by the test suite)

## Menu: initial focus, focus sounds, gamepad-friendly back, juicy hover (offset_transform, 4.7)
```gdscript
extends Control

@export var first_focus: Control
@export var focus_sound: AudioStreamPlayer

var _last_tween: Tween


func _ready() -> void:
	get_viewport().gui_focus_changed.connect(_on_focus_changed)
	for button in find_children("*", "BaseButton", true, false):
		var b := button as BaseButton
		b.offset_transform_enabled = true
		b.offset_transform_pivot_ratio = Vector2(0.5, 0.5)
		b.mouse_entered.connect(b.grab_focus.bind(true))  # 4.6+: focus without the keyboard outline
	if first_focus:
		first_focus.grab_focus.call_deferred()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and visible:
		hide()
		get_viewport().set_input_as_handled()


func _on_focus_changed(control: Control) -> void:
	if not is_ancestor_of(control):
		return
	if focus_sound:
		focus_sound.play()
	if _last_tween:
		_last_tween.kill()
	_last_tween = control.create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_last_tween.tween_property(control, "offset_transform_scale", Vector2(1.08, 1.08), 0.12).from(Vector2.ONE)
	_last_tween.tween_property(control, "offset_transform_scale", Vector2.ONE, 0.18)
```

## Mobile safe area (notches, rounded corners)
```gdscript
extends MarginContainer

@export var extra_margin := 16


func _ready() -> void:
	get_tree().root.size_changed.connect(_apply)
	_apply()


func _apply() -> void:
	var window := get_tree().root
	var safe := Rect2(DisplayServer.get_display_safe_area())
	var screen := Vector2(DisplayServer.screen_get_size())
	if safe.size == Vector2.ZERO or screen == Vector2.ZERO:
		return
	var to_ui := Vector2(window.get_visible_rect().size) / screen  # screen pixels -> UI units
	add_theme_constant_override("margin_left", int(safe.position.x * to_ui.x) + extra_margin)
	add_theme_constant_override("margin_top", int(safe.position.y * to_ui.y) + extra_margin)
	add_theme_constant_override("margin_right", int((screen.x - safe.end.x) * to_ui.x) + extra_margin)
	add_theme_constant_override("margin_bottom", int((screen.y - safe.end.y) * to_ui.y) + extra_margin)
```

## Inventory slot with drag and drop
```gdscript
class_name InventorySlot
extends PanelContainer

signal item_moved(from_slot: InventorySlot, to_slot: InventorySlot)

@export var item_icon: Texture2D:
	set(value):
		item_icon = value
		if is_node_ready():
			_icon.texture = value

@onready var _icon: TextureRect = $Icon


func _get_drag_data(_at_position: Vector2) -> Variant:
	if item_icon == null:
		return null
	var preview := TextureRect.new()
	preview.texture = item_icon
	preview.custom_minimum_size = Vector2(48, 48)
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	set_drag_preview(preview)
	return {"slot": self}


func _can_drop_data(_at_position: Vector2, data: Variant) -> bool:
	return data is Dictionary and data.get("slot") is InventorySlot and data["slot"] != self


func _drop_data(_at_position: Vector2, data: Variant) -> void:
	var from: InventorySlot = data["slot"]
	var swapped := item_icon
	item_icon = from.item_icon
	from.item_icon = swapped
	item_moved.emit(from, self)
```

## Health bar that follows a 3D target (unproject)
```gdscript
extends Control

@export var target: Node3D
@export var height_offset := 2.2


func _process(_delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	if target == null or cam == null:
		hide()
		return
	var world_pos := target.global_position + Vector3.UP * height_offset
	visible = not cam.is_position_behind(world_pos)
	if visible:
		position = cam.unproject_position(world_pos) - size * Vector2(0.5, 1.0)
```

## Settings screen in C# (focus, localization, volume)
```csharp
using Godot;

public partial class SettingsMenu : Control
{
    private HSlider _volume = null!;
    private OptionButton _language = null!;
    private static readonly string[] Locales = { "en", "it", "de", "ja" };

    public override void _Ready()
    {
        _volume = GetNode<HSlider>("%Volume");
        _language = GetNode<OptionButton>("%Language");
        _volume.AccessibilityName = Tr("SETTINGS_MASTER_VOLUME");
        _volume.ValueChanged += v => AudioServer.SetBusVolumeLinear(AudioServer.GetBusIndex("Master"), (float)v);
        foreach (string locale in Locales)
            _language.AddItem(TranslationServer.GetLocaleName(locale));
        _language.ItemSelected += i => TranslationServer.SetLocale(Locales[i]);
        _volume.GrabFocus();
    }
}
```
