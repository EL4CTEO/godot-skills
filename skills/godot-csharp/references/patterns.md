# C# patterns for Godot 4.7 (each block is a full file, built by the test suite)

## Character controller: cached StringNames, exports, signals, struct `with`
```csharp
using Godot;

[GlobalClass]
public partial class Player : CharacterBody3D
{
    private static readonly StringName MoveLeft = "move_left", MoveRight = "move_right";
    private static readonly StringName MoveUp = "move_up", MoveDown = "move_down", Jump = "jump";

    [Signal] public delegate void LandedEventHandler(float impactSpeed);

    [ExportGroup("Movement")]
    [Export(PropertyHint.Range, "0,20,0.1")] public float Speed { get; set; } = 6f;
    [Export] public float JumpVelocity { get; set; } = 4.5f;

    private float _gravity;
    private bool _wasOnFloor = true;

    public override void _Ready()
    {
        _gravity = (float)ProjectSettings.GetSetting("physics/3d/default_gravity").AsDouble();
    }

    public override void _PhysicsProcess(double delta)
    {
        Vector3 velocity = Velocity;
        if (!IsOnFloor())
            velocity.Y -= _gravity * (float)delta;
        else if (Input.IsActionJustPressed(Jump))
            velocity.Y = JumpVelocity;

        Vector2 input = Input.GetVector(MoveLeft, MoveRight, MoveUp, MoveDown);
        Vector3 dir = (Transform.Basis * new Vector3(input.X, 0, input.Y)).Normalized();
        velocity.X = dir.X * Speed;
        velocity.Z = dir.Z * Speed;

        float fallSpeed = -velocity.Y;
        Velocity = velocity;
        MoveAndSlide();

        if (IsOnFloor() && !_wasOnFloor)
            EmitSignal(SignalName.Landed, fallSpeed);
        _wasOnFloor = IsOnFloor();
    }
}
```

## Custom Resource as data, typed Godot collections at the boundary
```csharp
using Godot;
using Godot.Collections;

[GlobalClass]
public partial class ItemData : Resource
{
    [Export] public string Id { get; set; } = "";
    [Export] public Texture2D? Icon { get; set; }
    [Export(PropertyHint.Range, "1,999")] public int MaxStack { get; set; } = 99;
    [Export] public Dictionary<string, float> Stats { get; set; } = new();
    [Export] public Array<ItemData> Ingredients { get; set; } = new();
}
```

## Safe signal subscriptions (custom signals + capturing lambdas need `-=`)
```csharp
using Godot;

public partial class Hud : Control
{
    private Label _score = null!;
    private Health? _health;
    private Health.DiedEventHandler? _onDied;

    public override void _Ready()
    {
        _score = GetNode<Label>("%Score");
        _health = GetNodeOrNull<Health>("../Player/Health");
        if (_health is not null)
        {
            int deaths = 0;
            _onDied = () => _score.Text = $"Deaths: {++deaths}"; // captures -> keep a reference
            _health.Died += _onDied;
            _health.Changed += OnHealthChanged;
        }
    }

    public override void _ExitTree()
    {
        if (_health is not null && IsInstanceValid(_health))
        {
            _health.Died -= _onDied;
            _health.Changed -= OnHealthChanged;
        }
    }

    private void OnHealthChanged(int current, int maximum) =>
        _score.Text = string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0}/{1}", current, maximum);
}

public partial class Health : Node
{
    [Signal] public delegate void DiedEventHandler();
    [Signal] public delegate void ChangedEventHandler(int current, int maximum);
}
```

## Async: await signals, background work, back to the main thread
```csharp
using System.Threading.Tasks;
using Godot;

public partial class LevelLoader : Node
{
    [Signal] public delegate void LoadedEventHandler(Node level);

    public async void LoadAsync(string path)
    {
        ResourceLoader.LoadThreadedRequest(path);
        while (ResourceLoader.LoadThreadedGetStatus(path) == ResourceLoader.ThreadLoadStatus.InProgress)
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        if (!IsInstanceValid(this))
            return;
        var scene = (PackedScene)ResourceLoader.LoadThreadedGet(path);
        EmitSignal(SignalName.Loaded, scene.Instantiate());
    }

    public void ComputeInBackground(int[] data)
    {
        Task.Run(() =>
        {
            long sum = 0;
            foreach (int v in data) sum += v;
            Callable.From(() => GD.Print($"sum={sum}")).CallDeferred(); // touch the engine on the main thread
        });
    }
}
```

## Interop with GDScript nodes and Variant
```csharp
using Godot;

public partial class Bridge : Node
{
    public override void _Ready()
    {
        Node inventory = GetNode("Inventory");               // a node with a GDScript attached
        inventory.Call("add_item", "sword", 2);
        int count = inventory.Get("count").AsInt32();
        inventory.Connect("changed", Callable.From<int>(OnInventoryChanged));

        var helper = GD.Load<GDScript>("res://scripts/helper.gd").New().AsGodotObject();
        Variant result = helper.Call("compute", 21);
        GD.Print(count, " ", result.VariantType == Variant.Type.Int ? result.AsInt32() : 0);
    }

    // Callable from GDScript as bridge.Describe("x") (C# names are kept).
    public Variant Describe(string what) => Variant.From($"C# says {what}");

    private void OnInventoryChanged(int newCount) => GD.Print("inventory ", newCount);
}
```

## Tool script with an inspector button and editor-only code
```csharp
using Godot;

[Tool]
public partial class Scatter : Node3D
{
    [Export] public int Count { get; set; } = 10;
    [ExportToolButton("Scatter")] public Callable ScatterButton => Callable.From(DoScatter);

    private void DoScatter()
    {
        if (!Engine.IsEditorHint())
            return;
        foreach (Node child in GetChildren())
            child.QueueFree();
        var rng = new RandomNumberGenerator();
        for (int i = 0; i < Count; i++)
        {
            var marker = new Marker3D { Position = new Vector3(rng.RandfRange(-5, 5), 0, rng.RandfRange(-5, 5)) };
            AddChild(marker);
            marker.Owner = GetTree().EditedSceneRoot;
        }
    }
}
```

## Editor and hot-reload notes
- The editor rebuilds when it regains focus or when you press Build. A failed build keeps the old assembly running, so check `cs_build.py` output.
- `[Tool]` classes and `[GlobalClass]` resources need a successful build before the editor sees new members.
- If you see "assembly unloading failed", static state or a third-party library is holding the old assembly. Restart the editor. Avoid static references to Godot objects and static events.
- Debugging: run the game from an IDE with the Godot executable and `--path <project>` (Rider and VS Code C# Dev Kit support this). Breakpoints work in `[Tool]` code when the editor process is attached.
