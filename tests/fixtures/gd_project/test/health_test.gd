extends GdUnitTestSuite


func test_damage_clamps_to_zero() -> void:
	var h: HealthComponent = auto_free(HealthComponent.new())
	h.damage(500)
	assert_int(h.current).is_equal(0)
