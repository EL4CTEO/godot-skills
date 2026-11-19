class_name HealthComponent
extends Node

signal died
signal changed(current: int, maximum: int)

@export var max_health := 100
var current := max_health


func damage(amount: int) -> void:
	current = clampi(current - amount, 0, max_health)
	changed.emit(current, max_health)
	if current == 0:
		died.emit()
