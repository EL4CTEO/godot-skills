# Narrative patterns (compiled by the tests)

## Dialogue data as Resources (edit in the inspector, or build from JSON)
```gdscript
class_name DialogueChoiceData
extends Resource

@export var text_key := ""            ## translation key, shown with tr()
@export var next_id: StringName = &""  ## line to jump to
@export var condition := ""          ## e.g. "gold >= 10", empty = always
@export var set_flags: Dictionary[StringName, Variant] = {}
```
```gdscript
class_name DialogueLineData
extends Resource

@export var id: StringName = &""
@export var speaker: StringName = &""
@export var emotion: StringName = &"neutral"
@export_multiline var text_key := ""
@export var next_id: StringName = &""  ## empty = end of conversation
@export var choices: Array[DialogueChoiceData] = []
@export var set_flags: Dictionary[StringName, Variant] = {}
```
```gdscript
class_name DialogueGraph
extends Resource

@export var start_id: StringName = &"start"
@export var lines: Array[DialogueLineData] = []

var _by_id: Dictionary[StringName, DialogueLineData] = {}


func get_line(id: StringName) -> DialogueLineData:
	if _by_id.is_empty():
		for line in lines:
			_by_id[line.id] = line
	return _by_id.get(id)
```

## Story state (autoload "GameState")
```gdscript
class_name StoryState
extends Node

## Register as autoload "GameState". The class_name gives other scripts a typed handle.

signal flag_changed(name: StringName, value: Variant)

var flags: Dictionary[StringName, Variant] = {}

var _expr_cache: Dictionary[String, Expression] = {}


func get_flag(flag: StringName, default: Variant = null) -> Variant:
	return flags.get(flag, default)


func set_flag(flag: StringName, value: Variant) -> void:
	if flags.get(flag) == value:
		return
	flags[flag] = value
	flag_changed.emit(flag, value)


## Evaluates "gold >= 10 and not met_king" against current flags. Missing flags count as false/0.
func check(condition: String) -> bool:
	if condition.strip_edges().is_empty():
		return true
	var names := PackedStringArray()
	var values := []
	for key: StringName in flags:
		names.append(String(key))
		values.append(flags[key])
	var cache_key := condition + "|" + ",".join(names)
	var expr: Expression = _expr_cache.get(cache_key)
	if expr == null:
		expr = Expression.new()
		if expr.parse(condition, names) != OK:
			push_error("Bad condition '%s': %s" % [condition, expr.get_error_text()])
			return false
		_expr_cache[cache_key] = expr
	var result: Variant = expr.execute(values, self, false, true)  # const_calls_only: no side effects
	return not expr.has_execute_failed() and bool(result)


func to_save() -> Dictionary:
	return {"flags": flags.duplicate()}


func from_save(data: Dictionary) -> void:
	flags.clear()
	var saved: Dictionary = data.get("flags", {})
	for key in saved:
		flags[StringName(key)] = saved[key]
```

## Dialogue runner (logic only, no UI)
```gdscript
extends Node

## Emits what to show; the UI calls advance() and choose(). Uses the GameState autoload.

signal line_shown(line: DialogueLineData)
signal choices_shown(choices: Array[DialogueChoiceData])
signal dialogue_ended

var graph: DialogueGraph
var current: DialogueLineData

@onready var state: StoryState = get_node("/root/GameState")
var _visible_choices: Array[DialogueChoiceData] = []


func start(dialogue: DialogueGraph, from_id: StringName = &"") -> void:
	graph = dialogue
	_go(from_id if from_id != &"" else graph.start_id)


func advance() -> void:
	if current == null or not _visible_choices.is_empty():
		return  # waiting for a choice
	_go(current.next_id)


func choose(index: int) -> void:
	if index < 0 or index >= _visible_choices.size():
		return
	var choice := _visible_choices[index]
	_apply(choice.set_flags)
	_visible_choices.clear()
	_go(choice.next_id)


func _go(id: StringName) -> void:
	current = graph.get_line(id) if id != &"" else null
	if current == null:
		dialogue_ended.emit()
		return
	_apply(current.set_flags)
	line_shown.emit(current)
	_visible_choices.clear()
	for c in current.choices:
		if state.check(c.condition):
			_visible_choices.append(c)
	if not _visible_choices.is_empty():
		choices_shown.emit(_visible_choices)


func _apply(changes: Dictionary[StringName, Variant]) -> void:
	for key in changes:
		state.set_flag(key, changes[key])
```

## Typewriter dialogue box with choices (UI only)
```gdscript
extends CanvasLayer

signal advance_requested
signal choice_made(index: int)

@export var chars_per_second := 40.0
@export var blip_every := 3
@export var portraits: Dictionary[StringName, Texture2D] = {}

@onready var name_label: Label = %Name
@onready var text: RichTextLabel = %Text
@onready var portrait: TextureRect = %Portrait
@onready var choices_box: VBoxContainer = %Choices
@onready var blip: AudioStreamPlayer = %Blip

var _tween: Tween
var _input_block_until := 0
var _last_blip := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS  # works while the game is paused
	text.bbcode_enabled = true
	text.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	hide()


func show_line(speaker: StringName, body: String, emotion: StringName = &"neutral") -> void:
	show()
	_clear_choices()
	name_label.text = tr(String(speaker))
	portrait.texture = portraits.get(StringName("%s_%s" % [speaker, emotion]), portraits.get(speaker))
	text.text = body
	text.visible_ratio = 0.0
	_last_blip = 0
	_input_block_until = Time.get_ticks_msec() + 120  # a held button must not skip the line
	var duration := text.get_total_character_count() / chars_per_second
	if _tween:
		_tween.kill()
	_tween = create_tween()
	_tween.tween_method(_set_ratio, 0.0, 1.0, duration)


func _set_ratio(r: float) -> void:
	text.visible_ratio = r
	var shown := text.visible_characters
	if blip and shown - _last_blip >= blip_every:
		_last_blip = shown
		blip.play()


func is_typing() -> bool:
	return _tween != null and _tween.is_running()


func show_choices(labels: PackedStringArray) -> void:
	_clear_choices()
	for i in labels.size():
		var b := Button.new()
		b.text = "%d. %s" % [i + 1, labels[i]]
		b.pressed.connect(choice_made.emit.bind(i))
		choices_box.add_child(b)
	if choices_box.get_child_count() > 0:
		(choices_box.get_child(0) as Button).grab_focus()  # gamepad/keyboard ready


func _clear_choices() -> void:
	for c in choices_box.get_children():
		c.queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if not visible or Time.get_ticks_msec() < _input_block_until:
		return
	if event.is_action_pressed("ui_accept") or (event is InputEventMouseButton and event.pressed):
		get_viewport().set_input_as_handled()
		if is_typing():
			_tween.kill()
			text.visible_ratio = 1.0  # first press completes the line
		elif choices_box.get_child_count() == 0:
			advance_requested.emit()
	elif event is InputEventKey and event.pressed and choices_box.get_child_count() > 0:
		var n: int = event.keycode - KEY_1
		if n >= 0 and n < choices_box.get_child_count():
			choice_made.emit(n)
```

## Quests as Resources + QuestLog autoload
```gdscript
class_name QuestData
extends Resource

@export var id: StringName = &""
@export var title_key := ""
@export var objective_ids: Array[StringName] = []
@export var objective_required: PackedInt32Array = []  ## same order as objective_ids
@export var reward_flags: Dictionary[StringName, Variant] = {}
```
```gdscript
extends Node

## Autoload "QuestLog". Runtime progress lives here, never in the shared QuestData resources.

signal quest_started(quest: QuestData)
signal objective_updated(quest: QuestData, objective: StringName, count: int, required: int)
signal quest_completed(quest: QuestData)

var active: Dictionary[StringName, QuestData] = {}
var progress: Dictionary[StringName, Dictionary] = {}  # quest id -> {objective id: count}
var completed: Dictionary[StringName, bool] = {}

@onready var state: StoryState = get_node("/root/GameState")


func start(quest: QuestData) -> void:
	if active.has(quest.id) or completed.has(quest.id):
		return
	active[quest.id] = quest
	var p := {}
	for o in quest.objective_ids:
		p[o] = 0
	progress[quest.id] = p
	quest_started.emit(quest)


## Gameplay reports generic events, e.g. report(&"kill_wolf") or report(&"talk_elder").
func report(objective: StringName, amount := 1) -> void:
	for quest: QuestData in active.values():
		var i := quest.objective_ids.find(objective)
		if i == -1:
			continue
		var p: Dictionary = progress[quest.id]
		var required := quest.objective_required[i] if i < quest.objective_required.size() else 1
		p[objective] = mini(int(p[objective]) + amount, required)
		objective_updated.emit(quest, objective, p[objective], required)
		if _is_done(quest):
			_complete(quest)


func _is_done(quest: QuestData) -> bool:
	var p: Dictionary = progress[quest.id]
	for i in quest.objective_ids.size():
		var required := quest.objective_required[i] if i < quest.objective_required.size() else 1
		if int(p[quest.objective_ids[i]]) < required:
			return false
	return true


func _complete(quest: QuestData) -> void:
	active.erase(quest.id)
	completed[quest.id] = true
	for key in quest.reward_flags:
		state.set_flag(key, quest.reward_flags[key])
	quest_completed.emit(quest)
```

## Cutscene that waits for dialogue (Tween.tween_await, 4.7)
```gdscript
extends Node3D

signal dialogue_finished

@export var camera: Camera3D
@export var npc: Node3D


func play_intro() -> void:
	get_tree().paused = true
	var tween := create_tween().set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tween.tween_property(camera, "global_position", npc.global_position + Vector3(0, 1.6, 2.5), 1.2)
	tween.tween_callback(_start_dialogue)
	tween.tween_await(dialogue_finished).set_timeout(120.0)  # tween pauses here until the signal
	tween.tween_property(camera, "fov", 75.0, 0.5)
	await tween.finished
	get_tree().paused = false


func _start_dialogue() -> void:
	# Hook your runner here; emit dialogue_finished from its dialogue_ended signal.
	dialogue_finished.emit.call_deferred()
```

## Typewriter in C#
```csharp
using Godot;

public partial class TypewriterLabel : RichTextLabel
{
    [Signal] public delegate void FinishedEventHandler();

    [Export] public float CharsPerSecond { get; set; } = 40f;

    private Tween? _tween;

    public bool IsTyping => _tween is not null && _tween.IsRunning();

    public void Play(string bbcode)
    {
        BbcodeEnabled = true;
        VisibleCharactersBehavior = TextServer.VisibleCharactersBehavior.CharsAfterShaping;
        Text = bbcode;
        VisibleRatio = 0f;
        _tween?.Kill();
        _tween = CreateTween();
        _tween.TweenProperty(this, "visible_ratio", 1f, GetTotalCharacterCount() / CharsPerSecond);
        _tween.Finished += () => EmitSignal(SignalName.Finished);
    }

    public void Complete()
    {
        _tween?.Kill();
        VisibleRatio = 1f;
        EmitSignal(SignalName.Finished);
    }
}
```
