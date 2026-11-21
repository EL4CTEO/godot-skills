# Game feel patterns (compiled by the tests)

## Juice autoload: settings-aware entry point for all feedback
```gdscript
extends Node

## Autoload "Juice". Gameplay calls Juice.impact(strength); components read the settings.

signal shake_requested(trauma: float)

var shake_scale := 1.0      ## 0..1 from the accessibility settings
var flashes_enabled := true
var rumble_enabled := true
var hitstop_enabled := true

var _hitstop_until := 0


func impact(strength: float, device := 0) -> void:
	strength = clampf(strength, 0.0, 1.0)
	shake_requested.emit(strength * 0.6 * shake_scale)
	if hitstop_enabled and strength > 0.3:
		hitstop(0.04 + strength * 0.1)
	if rumble_enabled:
		Input.start_joy_vibration(device, strength * 0.6, strength, 0.08 + strength * 0.12)


func hitstop(seconds: float, scale := 0.05) -> void:
	var until := Time.get_ticks_msec() + int(seconds * 1000.0)
	if until <= _hitstop_until:
		return  # a longer hit-stop is already running
	_hitstop_until = until
	Engine.time_scale = scale
	# ignore_time_scale = true, otherwise the timer itself runs 20x slower
	await get_tree().create_timer(seconds, true, false, true).timeout
	if Time.get_ticks_msec() >= _hitstop_until:
		Engine.time_scale = 1.0


func slow_motion(scale := 0.3, hold := 0.5) -> void:
	var t := create_tween().set_ignore_time_scale(true)
	t.tween_property(Engine, "time_scale", scale, 0.08)
	t.tween_interval(hold)
	t.tween_property(Engine, "time_scale", 1.0, 0.25)
```

## 3D camera shake (trauma + noise, offsets and roll)
```gdscript
extends Camera3D

@export var max_offset := Vector2(0.4, 0.3)
@export var max_roll_degrees := 3.0
@export var decay := 1.6
@export var frequency := 18.0

var trauma := 0.0
var _noise := FastNoiseLite.new()
var _t := 0.0
var _base_roll := 0.0


func _ready() -> void:
	_noise.seed = randi()
	_base_roll = rotation.z


func add_trauma(amount: float) -> void:
	trauma = minf(trauma + amount, 1.0)


func _process(delta: float) -> void:
	_t += delta * frequency
	trauma = maxf(trauma - decay * delta, 0.0)
	var s := trauma * trauma  # squared: small hits stay subtle, big ones feel violent
	h_offset = max_offset.x * s * _noise.get_noise_2d(_t, 0.0)
	v_offset = max_offset.y * s * _noise.get_noise_2d(0.0, _t)
	rotation.z = _base_roll + deg_to_rad(max_roll_degrees) * s * _noise.get_noise_2d(_t, _t)
```

## Hit flash (shader + component)
```gdshader
shader_type canvas_item;

uniform vec4 flash_color : source_color = vec4(1.0);
uniform float flash : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	vec4 tex = texture(TEXTURE, UV) * COLOR;
	COLOR = vec4(mix(tex.rgb, flash_color.rgb, flash), tex.a);
}
```
```gdshader
shader_type spatial;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform vec4 flash_color : source_color = vec4(1.0);
uniform float flash : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	vec3 base = albedo.rgb * texture(albedo_tex, UV).rgb;
	ALBEDO = mix(base, flash_color.rgb, flash);
	EMISSION = flash_color.rgb * flash * 2.0;
}
```
```gdscript
extends Node

## HitFlash component: point it at a CanvasItem or GeometryInstance3D using a material with "flash".

@export var target: Node
@export var duration := 0.1

var _tween: Tween


func flash() -> void:
	var mat := _material()
	if mat == null:
		return
	if _tween:
		_tween.kill()
	_tween = create_tween().set_ignore_time_scale(true)  # visible during hit-stop
	mat.set_shader_parameter(&"flash", 1.0)
	_tween.tween_method(func(v: float) -> void: mat.set_shader_parameter(&"flash", v), 1.0, 0.0, duration)


func _material() -> ShaderMaterial:
	if target is CanvasItem:
		return (target as CanvasItem).material as ShaderMaterial
	if target is GeometryInstance3D:
		return (target as GeometryInstance3D).material_override as ShaderMaterial
	return null
```

## Squash and stretch on the visual child
```gdscript
extends Node2D

## Put on the Sprite (visual) node, not the CharacterBody2D.

var _tween: Tween


func squash(amount := 0.25, time := 0.18) -> void:
	_play(Vector2(1.0 + amount, 1.0 - amount), time)


func stretch(amount := 0.2, time := 0.15) -> void:
	_play(Vector2(1.0 - amount, 1.0 + amount), time)


func _play(peak: Vector2, time: float) -> void:
	if _tween:
		_tween.kill()
	scale = peak
	_tween = create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_tween.tween_property(self, "scale", Vector2.ONE, time)
```

## Knockback that decays (2D character)
```gdscript
extends CharacterBody2D

@export var move_speed := 220.0
@export var knockback_decay := 2400.0
@export var stun_time := 0.15

var knockback := Vector2.ZERO
var _stunned_until := 0


func hit(from: Vector2, force := 450.0) -> void:
	knockback = (global_position - from).normalized() * force
	_stunned_until = Time.get_ticks_msec() + int(stun_time * 1000.0)


func _physics_process(delta: float) -> void:
	var input := Vector2.ZERO
	if Time.get_ticks_msec() >= _stunned_until:
		input = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	knockback = knockback.move_toward(Vector2.ZERO, knockback_decay * delta)
	velocity = input * move_speed + knockback
	move_and_slide()
```

## Damage numbers
```gdscript
extends Label

## DamageNumber scene: a Label with this script. Call popup() right after add_child.


func popup(amount: int, world_pos: Vector2, crit := false) -> void:
	text = str(amount)
	global_position = world_pos - size * 0.5
	pivot_offset = size * 0.5
	modulate = Color(1.0, 0.85, 0.2) if crit else Color.WHITE
	scale = Vector2.ONE * (1.6 if crit else 1.0)
	var drift := Vector2(randf_range(-12.0, 12.0), -40.0)
	var t := create_tween().set_parallel()
	t.tween_property(self, "position", drift, 0.7).as_relative().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.tween_property(self, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_BACK)
	t.tween_property(self, "modulate:a", 0.0, 0.3).set_delay(0.4)
	t.chain().tween_callback(queue_free)
```

## Juicy button (offset_transform, safe inside containers)
```gdscript
extends Button

var _tween: Tween


func _ready() -> void:
	offset_transform_pivot_ratio = Vector2(0.5, 0.5)
	mouse_entered.connect(_to.bind(1.06))
	focus_entered.connect(_to.bind(1.06))
	mouse_exited.connect(_to.bind(1.0))
	focus_exited.connect(_to.bind(1.0))
	button_down.connect(_to.bind(0.92))
	button_up.connect(_to.bind(1.06))


func _to(s: float) -> void:
	if _tween:
		_tween.kill()
	_tween = create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT).set_ignore_time_scale(true)
	_tween.tween_property(self, "offset_transform_scale", Vector2.ONE * s, 0.12)
```

## Camera2D shake in C#
```csharp
using Godot;

public partial class ShakeCamera2D : Camera2D
{
    [Export] public Vector2 MaxOffset { get; set; } = new(24, 16);
    [Export] public float Decay { get; set; } = 1.5f;

    private readonly FastNoiseLite _noise = new() { Frequency = 0.5f };
    private float _trauma;
    private float _time;

    public void AddTrauma(float amount) => _trauma = Mathf.Min(_trauma + amount, 1f);

    public override void _Process(double delta)
    {
        _time += (float)delta * 30f;
        _trauma = Mathf.Max(_trauma - Decay * (float)delta, 0f);
        float s = _trauma * _trauma;
        Offset = new Vector2(
            MaxOffset.X * s * _noise.GetNoise2D(_time, 0f),
            MaxOffset.Y * s * _noise.GetNoise2D(0f, _time));
    }
}
```
