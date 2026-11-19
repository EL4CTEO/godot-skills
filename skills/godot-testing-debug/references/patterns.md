# Testing and debugging patterns (compiled by the test suite, GdUnit4 6.2.2 / gdUnit4Net 5.1)

## Unit tests: values, signals, errors, parameterized
```gdscript
extends GdUnitTestSuite

var health: HealthComponent


func before_test() -> void:
	health = auto_free(HealthComponent.new())
	health.max_health = 100
	health.current = 100


func test_damage_reduces_health() -> void:
	health.damage(30)
	assert_int(health.current).is_equal(70)


func test_died_emitted_once_at_zero() -> void:
	monitor_signals(health)
	health.damage(150)
	await assert_signal(health).is_emitted("died")
	assert_int(health.current).is_equal(0)


func test_damage_values(amount: int, expected: int, test_parameters := [[10, 90], [100, 0], [0, 100]]) -> void:
	health.damage(amount)
	assert_int(health.current).is_equal(expected)
```

## Mocks and spies
```gdscript
extends GdUnitTestSuite


func test_spy_tracks_calls() -> void:
	var h: HealthComponent = spy(auto_free(HealthComponent.new()))
	h.damage(5)
	h.damage(5)
	verify(h, 2).damage(5)


func test_mock_returns_canned_value() -> void:
	var m: Variant = mock(RandomNumberGenerator)
	do_return(4).on(m).randi_range(any_int(), any_int())
	assert_int(m.randi_range(1, 6)).is_equal(4)
```

## Scene runner: drive a real scene with simulated input and frames
```gdscript
extends GdUnitTestSuite


func test_main_scene_shows_score_after_ready() -> void:
	var runner := scene_runner("res://scenes/main.tscn")
	await runner.simulate_frames(5)
	var label := runner.find_child("ScoreLabel") as Label
	assert_str(label.text).is_equal("Score: 10")


func test_jump_action_reaches_the_scene() -> void:
	var runner := scene_runner("res://scenes/main.tscn")
	runner.simulate_action_pressed("jump")
	await runner.simulate_frames(2)
	assert_bool(Input.is_action_pressed("jump")).is_false()  # pressed+released in the same simulation
```

## C# tests (pure logic + Godot runtime + scene runner)
```csharp
namespace Game.Tests;

using GdUnit4;
using Godot;
using static GdUnit4.Assertions;

[TestSuite]
public class InventoryTest
{
    [TestCase]
    public void StackSplitsAtMax() // pure C#: no [RequireGodotRuntime] needed, runs fast
    {
        int full = System.Math.Min(150, 99);
        AssertThat(full).IsEqual(99);
        AssertThat(150 - full).IsEqual(51);
    }

    [TestCase]
    [RequireGodotRuntime] // touches Godot types
    public void NodeNameIsKept()
    {
        var node = AutoFree(new Node3D { Name = "Chest" })!;
        AssertThat(node.Name.ToString()).IsEqual("Chest");
    }

    [TestCase]
    [RequireGodotRuntime]
    public async System.Threading.Tasks.Task MainSceneBoots()
    {
        ISceneRunner runner = ISceneRunner.Load("res://scenes/main.tscn", true);
        await runner.SimulateFrames(5);
        AssertThat(runner.Scene()).IsNotNull();
    }
}
```

## In-game error reporter with a custom Logger (4.5+)
```gdscript
extends Node

class ReportLogger extends Logger:
	var lines: Array[String] = []
	var mutex := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, script_backtraces: Array[ScriptBacktrace]) -> void:
		var msg := "[%d] %s:%d %s() %s %s" % [error_type, file, line, function, code, rationale]
		for bt in script_backtraces:
			msg += "\n" + bt.format()
		mutex.lock()  # loggers can be called from any thread
		lines.append(msg)
		mutex.unlock()

	func _log_message(message: String, error: bool) -> void:
		if error:
			mutex.lock()
			lines.append(message)
			mutex.unlock()

var logger := ReportLogger.new()


func _ready() -> void:
	OS.add_logger(logger)


func _exit_tree() -> void:
	OS.remove_logger(logger)


func build_report() -> String:
	logger.mutex.lock()
	var text := "\n".join(logger.lines.slice(-50))
	logger.mutex.unlock()
	return "%s %s\n%s" % [ProjectSettings.get_setting("application/config/version", "dev"), OS.get_name(), text]
```

## Debug-only helpers that vanish in release builds
```gdscript
extends Node3D


func _process(_delta: float) -> void:
	if not OS.is_debug_build():
		return
	if Input.is_physical_key_pressed(KEY_F3):
		print_rich("[color=yellow]pos=%s vel=%s[/color]" % [global_position, get_meta(&"velocity", Vector3.ZERO)])


func _check_invariants(health: int) -> void:
	assert(health >= 0, "health must never be negative")  # stripped from release builds
	if health > 1000:
		push_warning("suspicious health value %d" % health)
```
