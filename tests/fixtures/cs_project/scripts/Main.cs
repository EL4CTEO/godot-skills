using Godot;

namespace CsFixture;

public partial class Main : Node2D
{
    private Label _scoreLabel = null!;

    public override void _Ready()
    {
        _scoreLabel = GetNode<Label>("ScoreLabel");
        Events.Instance.ScoreChanged += OnScoreChanged;
        Events.Instance.EmitSignal(Events.SignalName.ScoreChanged, 10);
        GD.Print("CS_FIXTURE_READY ", _scoreLabel.Text);
    }

    public override void _ExitTree() => Events.Instance.ScoreChanged -= OnScoreChanged;

    private void OnScoreChanged(int newScore) => _scoreLabel.Text = $"Score: {newScore}";
}
