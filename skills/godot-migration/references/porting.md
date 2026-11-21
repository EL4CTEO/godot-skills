# Porting patterns (compiled by the tests)

## Godot 3 GDScript → 4.7 (before/after)
```gdscript
# snippet: skip  (Godot 3 code, shown for comparison; it does not compile on 4.7)
extends KinematicBody
signal died
export(int) var max_health = 100 setget set_max_health
onready var anim = $AnimationPlayer
var velocity = Vector3()

func _ready():
	$Hurtbox.connect("area_entered", self, "_on_hit", [10])

func _physics_process(delta):
	velocity.y -= 9.8 * delta
	velocity = move_and_slide_with_snap(velocity, Vector3.DOWN, Vector3.UP, true)

func _on_hit(area, dmg):
	$Tween.interpolate_property(self, "scale", Vector3(1.2, 1.2, 1.2), Vector3.ONE, 0.2)
	$Tween.start()
	yield($Tween, "tween_completed")
	emit_signal("died")

func set_max_health(v):
	max_health = max(v, 1)
```
```gdscript
extends CharacterBody3D

signal died

@export var max_health := 100:
	set(value):
		max_health = maxi(value, 1)

@onready var anim: AnimationPlayer = $AnimationPlayer


func _ready() -> void:
	floor_snap_length = 0.3  # replaces the snap vector of move_and_slide_with_snap
	$Hurtbox.area_entered.connect(_on_hit.bind(10))


func _physics_process(delta: float) -> void:
	velocity += get_gravity() * delta
	move_and_slide()  # no arguments; velocity is a property and is updated in place


func _on_hit(_area: Area3D, _damage: int) -> void:
	var tween := create_tween()  # no Tween node needed
	tween.tween_property(self, "scale", Vector3.ONE, 0.2).from(Vector3.ONE * 1.2)
	await tween.finished
	died.emit()
```

## Godot 3 C# → 4.7 C#
```csharp
// snippet: skip  (Godot 3 C#, shown for comparison)
public class Enemy : KinematicBody
{
    [Signal] delegate void Died(int score);
    [Export] public int Score = 10;
    public override void _Ready() { GetNode("Hurtbox").Connect("area_entered", this, nameof(OnHit)); }
    public override void _PhysicsProcess(float delta) { MoveAndSlide(new Vector3(0, -9.8f, 0), Vector3.Up); }
    void OnHit(Area area) { EmitSignal(nameof(Died), Score); QueueFree(); }
}
```
```csharp
using Godot;

public partial class Enemy : CharacterBody3D
{
    [Signal] public delegate void DiedEventHandler(int score);

    [Export] public int Score { get; set; } = 10;

    public override void _Ready()
    {
        GetNode<Area3D>("Hurtbox").AreaEntered += OnHit;
    }

    public override void _PhysicsProcess(double delta)
    {
        Velocity += GetGravity() * (float)delta;
        MoveAndSlide();
    }

    private void OnHit(Area3D area)
    {
        EmitSignal(SignalName.Died, Score);
        QueueFree();
    }
}
```

## Unity habits in Godot: components as child nodes
```csharp
using Godot;

/// <summary>Unity-style lookups. Prefer exported references or %UniqueNames for hot paths.</summary>
public static class NodeComponentExtensions
{
    /// <summary>Like GetComponent: first direct child of type T, or null.</summary>
    public static T? GetComponent<T>(this Node node) where T : Node
    {
        foreach (Node child in node.GetChildren())
        {
            if (child is T match)
                return match;
        }
        return null;
    }

    /// <summary>Like GetComponentInParent: nearest ancestor of type T, or null.</summary>
    public static T? GetComponentInParent<T>(this Node node) where T : Node
    {
        for (Node? p = node.GetParent(); p != null; p = p.GetParent())
        {
            if (p is T match)
                return match;
        }
        return null;
    }
}

[GlobalClass]
public partial class HealthComponent : Node
{
    [Signal] public delegate void DiedEventHandler();
    [Signal] public delegate void ChangedEventHandler(int current, int max);

    [Export] public int Max { get; set; } = 100;
    public int Current { get; private set; }

    public override void _Ready() => Current = Max;

    public void Damage(int amount)
    {
        if (Current <= 0)
            return;
        Current = Mathf.Max(Current - amount, 0);
        EmitSignal(SignalName.Changed, Current, Max);
        if (Current == 0)
            EmitSignal(SignalName.Died);
    }
}
```

## ScriptableObject → Resource
```csharp
using Godot;

[GlobalClass]
public partial class WeaponData : Resource
{
    [Export] public string DisplayName { get; set; } = "";
    [Export] public int Damage { get; set; } = 10;
    [Export(PropertyHint.Range, "0.05,5,0.05")] public float Cooldown { get; set; } = 0.5f;
    [Export] public PackedScene? Projectile { get; set; }
}
```
```gdscript
class_name EnemyData
extends Resource

## Create instances with right-click > New Resource > EnemyData. Shared .tres files are shared
## instances: call duplicate() before changing runtime values per enemy.

@export var display_name := ""
@export var max_health := 50
@export_range(0.5, 20.0, 0.5) var speed := 3.0
@export var drops: Array[StringName] = []
```

## Coroutines → await
```csharp
using Godot;

public partial class Spawner : Node3D
{
    [Export] public PackedScene? Enemy { get; set; }
    [Export] public int Count { get; set; } = 5;

    // Unity: IEnumerator SpawnWave() { ... yield return new WaitForSeconds(0.5f); }
    public async void SpawnWave()
    {
        for (int i = 0; i < Count && Enemy != null; i++)
        {
            var e = Enemy.Instantiate<Node3D>();
            AddChild(e);
            e.Position = new Vector3(i * 2f, 0f, 0f);
            await ToSignal(GetTree().CreateTimer(0.5), SceneTreeTimer.SignalName.Timeout);
            if (!IsInsideTree())
                return; // the spawner was freed while waiting
        }
    }
}
```

## Checklist after any upgrade
1. `migrate_scan.py` shows no `error` findings; review `warn`/`info`.
2. `gd_check.py` and `cs_build.py` are clean.
3. `run_godot.py smoke` on the main scene and on every level scene shows no errors.
4. The unit tests pass (`test_run.py`).
5. Manual pass in the editor: lighting/post-processing, physics feel (jump height, slopes), UI scaling (stretch mode), audio buses, input on gamepad.
6. Upgrade Project Files, commit `*.uid`, re-export every platform with 4.7.2 templates.
