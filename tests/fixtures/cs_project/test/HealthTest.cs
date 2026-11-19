namespace CsFixture.Tests;

using GdUnit4;
using static GdUnit4.Assertions;

[TestSuite]
public class HealthTest
{
    [TestCase]
    [RequireGodotRuntime]
    public void DamageClampsToZero()
    {
        var health = AutoFree(new Health())!;
        health._Ready();
        health.Damage(500);
        AssertThat(health.Current).IsEqual(0);
    }
}
