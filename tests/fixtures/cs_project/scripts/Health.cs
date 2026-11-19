using Godot;

namespace CsFixture;

[GlobalClass]
public partial class Health : Node
{
    [Signal] public delegate void DiedEventHandler();
    [Signal] public delegate void ChangedEventHandler(int current, int maximum);

    [Export] public int MaxHealth { get; set; } = 100;
    public int Current { get; private set; }

    public override void _Ready() => Current = MaxHealth;

    public void Damage(int amount)
    {
        Current = Mathf.Clamp(Current - amount, 0, MaxHealth);
        EmitSignal(SignalName.Changed, Current, MaxHealth);
        if (Current == 0)
            EmitSignal(SignalName.Died);
    }
}
