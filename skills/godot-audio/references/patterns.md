# Audio patterns (compiled by the test suite)

## Audio autoload: linear volume settings, SFX pool, UI sounds
```gdscript
extends Node

const POOL_SIZE := 12

var _pool: Array[AudioStreamPlayer] = []
var _next := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in POOL_SIZE:
		var p := AudioStreamPlayer.new()
		p.bus = &"SFX"
		add_child(p)
		_pool.append(p)


func set_volume(bus_name: StringName, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	AudioServer.set_bus_volume_linear(idx, clampf(linear, 0.0, 1.0))
	AudioServer.set_bus_mute(idx, linear <= 0.001)


func play_sfx(stream: AudioStream, volume_db := 0.0, pitch := 1.0) -> void:
	var p := _pool[_next]
	_next = (_next + 1) % POOL_SIZE
	p.stream = stream
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.play()


func play_at(stream: AudioStream, world_pos: Vector3, parent: Node) -> void:
	var p := AudioStreamPlayer3D.new()
	p.stream = stream
	p.bus = &"SFX"
	p.attenuation_filter_cutoff_hz = 6000.0
	parent.add_child(p)
	p.global_position = world_pos
	p.finished.connect(p.queue_free)
	p.play()
```

## Adaptive music with AudioStreamInteractive
```gdscript
extends AudioStreamPlayer

@export var combat_clip := &"combat"
@export var explore_clip := &"explore"

var _in_combat := false


func _ready() -> void:
	bus = &"Music"
	process_mode = Node.PROCESS_MODE_ALWAYS
	play()


func set_combat(active: bool) -> void:
	if active == _in_combat or not playing:
		return
	_in_combat = active
	var pb := get_stream_playback() as AudioStreamPlaybackInteractive
	if pb:
		pb.switch_to_clip_by_name(combat_clip if active else explore_clip)  # transitions defined on the stream
```

## Building an interactive stream in code (normally done in the inspector)
```gdscript
extends Node


func build(explore: AudioStream, combat: AudioStream) -> AudioStreamInteractive:
	var s := AudioStreamInteractive.new()
	s.clip_count = 2
	s.set_clip_name(0, &"explore")
	s.set_clip_stream(0, explore)
	s.set_clip_name(1, &"combat")
	s.set_clip_stream(1, combat)
	s.initial_clip = 0
	s.add_transition(0, 1, AudioStreamInteractive.TRANSITION_FROM_TIME_NEXT_BAR,
			AudioStreamInteractive.TRANSITION_TO_TIME_START, AudioStreamInteractive.FADE_CROSS, 1.0)
	s.add_transition(1, 0, AudioStreamInteractive.TRANSITION_FROM_TIME_NEXT_BAR,
			AudioStreamInteractive.TRANSITION_TO_TIME_SAME_POSITION, AudioStreamInteractive.FADE_CROSS, 2.0)
	return s
```

## Vertical layering with AudioStreamSynchronized
```gdscript
extends AudioStreamPlayer

## stream must be an AudioStreamSynchronized: 0 = base, 1 = percussion, 2 = strings
var _targets: Array[float] = [0.0, -80.0, -80.0]


func set_intensity(level: int) -> void:
	_targets = [0.0, 0.0 if level >= 1 else -80.0, 0.0 if level >= 2 else -80.0]


func _process(delta: float) -> void:
	var sync := stream as AudioStreamSynchronized
	if sync == null:
		return
	for i in mini(sync.stream_count, _targets.size()):
		var current := sync.get_sync_stream_volume(i)
		sync.set_sync_stream_volume(i, move_toward(current, _targets[i], 60.0 * delta))
```

## Procedural square-wave beep (AudioStreamGenerator)
```gdscript
extends AudioStreamPlayer

@export var frequency := 440.0

var _phase := 0.0
var _playback: AudioStreamGeneratorPlayback


func _ready() -> void:
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = 44100.0
	gen.buffer_length = 0.1
	stream = gen
	play()
	_playback = get_stream_playback()


func _process(_delta: float) -> void:
	if _playback == null:
		return
	var increment := frequency / 44100.0
	for i in _playback.get_frames_available():
		var s := 0.2 if _phase < 0.5 else -0.2
		_playback.push_frame(Vector2(s, s))
		_phase = fmod(_phase + increment, 1.0)
```

## C#: volume slider bound to a bus
```csharp
using Godot;

public partial class VolumeSlider : HSlider
{
    [Export] public StringName BusName { get; set; } = "Master";
    private int _bus;

    public override void _Ready()
    {
        _bus = AudioServer.GetBusIndex(BusName);
        MinValue = 0;
        MaxValue = 1;
        Step = 0.01;
        Value = AudioServer.GetBusVolumeLinear(_bus);
        ValueChanged += v =>
        {
            AudioServer.SetBusVolumeLinear(_bus, (float)v);
            AudioServer.SetBusMute(_bus, v <= 0.001);
        };
    }
}
```
