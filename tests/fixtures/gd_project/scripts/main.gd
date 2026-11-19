extends Node2D

var score := 0


func _ready() -> void:
	Events.score_changed.connect(_on_score_changed)
	Events.score_changed.emit(10)
	print("GD_FIXTURE_READY ", score)


func _on_score_changed(new_score: int) -> void:
	score = new_score
	$ScoreLabel.text = "Score: %d" % score
