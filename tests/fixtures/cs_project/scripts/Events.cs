using Godot;

namespace CsFixture;

/// <summary>Global event bus (autoload "Events"). Only signals live here.</summary>
public partial class Events : Node
{
    public static Events Instance { get; private set; } = null!;

    [Signal] public delegate void PlayerDiedEventHandler();
    [Signal] public delegate void ScoreChangedEventHandler(int newScore);

    public override void _EnterTree() => Instance = this;
}
