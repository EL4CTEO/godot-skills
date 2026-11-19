## Global event bus (autoload "Events"). Only signals live here.
extends Node

signal player_died
signal score_changed(new_score: int)
signal level_loaded(level_name: String)
